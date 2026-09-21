from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
import logging
import io
import json
import jwt
import bcrypt
import pandas as pd
from openpyxl import Workbook

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cds")

app = FastAPI(title="Control Data Stock & Production")
api = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Roles, modules & permissions
# ---------------------------------------------------------------------------
ROLE_LABELS = {
    "admin": "Administrator",
    "management": "Management",
    "production_planning": "Production Planning (PPIC)",
    "production_control": "Production Control (PC)",
    "smt": "SMT",
    "assembly": "Assembly (LAMP ASSY)",
}

MODULES = {
    "smt_production": "Produksi SMT & ASSY",
    "smt_stock": "Stock SMT",
    "production_needs": "Kebutuhan vs Stock",
    "variance": "Variance Stock",
    "items": "Master Item",
    "audit": "Audit Trail",
    "users": "Manajemen User",
}
LEVELS = ["none", "read", "write"]
LEVEL_LABELS = {"none": "Tidak ada", "read": "Lihat", "write": "Ubah"}

ROLE_DEFAULT_PERMS = {
    "admin": {m: "write" for m in MODULES},
    "management": {**{m: "write" for m in MODULES}, "users": "none", "audit": "read"},
    "production_planning": {"smt_production": "write", "smt_stock": "write",
                            "production_needs": "write", "variance": "write", "items": "write", "users": "none"},
    "production_control": {"smt_production": "write", "smt_stock": "read",
                           "production_needs": "read", "variance": "write", "items": "read", "users": "none"},
    "smt": {"smt_production": "write", "smt_stock": "write",
            "production_needs": "read", "variance": "read", "items": "read", "users": "none"},
    "assembly": {"smt_production": "write", "smt_stock": "read",
                 "production_needs": "read", "variance": "read", "items": "read", "users": "none"},
}


def effective_perms(user: dict) -> Dict[str, str]:
    base = dict(ROLE_DEFAULT_PERMS.get(user.get("role"), {}))
    base.setdefault("audit", "none")
    for m, lvl in (user.get("permissions") or {}).items():
        if m in MODULES and lvl in LEVELS:
            base[m] = lvl
    if user.get("role") == "admin":
        base["users"] = "write"
    return base


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def public_user(user: dict) -> dict:
    user = dict(user)
    user["id"] = str(user.pop("_id"))
    user.pop("password_hash", None)
    user["role_label"] = ROLE_LABELS.get(user.get("role"), user.get("role"))
    user["permissions"] = user.get("permissions") or {}
    user["email"] = user.get("email") or ""
    user["notify"] = user.get("notify") or {"enabled": False, "modules": []}
    user["effective_permissions"] = effective_perms(user)
    user["is_main_admin"] = user.get("email") == os.environ.get("ADMIN_EMAIL", "").lower()
    return user


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=401, detail="User tidak ditemukan")
    return public_user(user)


def require_perm(module: str, level: str):
    async def dep(user: dict = Depends(get_current_user)):
        have = user["effective_permissions"].get(module, "none")
        if LEVELS.index(have) < LEVELS.index(level):
            msg = "Anda tidak memiliki akses ke modul ini" if level == "read" else "Anda tidak memiliki akses untuk mengubah data ini"
            raise HTTPException(status_code=403, detail=msg)
        return user
    return dep


def oid(x: str) -> ObjectId:
    try:
        return ObjectId(x)
    except Exception:
        raise HTTPException(status_code=400, detail="ID tidak valid")


def clean(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        f = float(v)
        return default if f != f else f
    except Exception:
        return default


def r1(v):
    return round(v, 2)


# ---------------------------------------------------------------------------
# Audit trail & notifications
# ---------------------------------------------------------------------------
DATA_MODULES = ["smt_production", "smt_stock", "production_needs", "variance", "items"]


def client_info(request: Optional[Request]):
    if request is None:
        return "", ""
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
    return ip, request.headers.get("user-agent", "")[:200]


async def log_audit(request: Optional[Request], user: dict, action: str, module: str,
                    record_id: str = "", before: Optional[dict] = None, after: Optional[dict] = None, note: str = ""):
    ip, ua = client_info(request)
    ref = after or before or {}
    await db.audit_log.insert_one({
        "ts": datetime.now(timezone.utc).isoformat(), "user_id": user["id"], "user_name": user.get("name", ""),
        "username": user.get("username", ""), "role": user.get("role", ""), "action": action, "module": module,
        "record_id": record_id, "ics_no": ref.get("ics_no", ""), "type": ref.get("type", ""), "date": ref.get("date", ""),
        "before": strip_meta(before), "after": strip_meta(after), "note": note, "ip": ip, "user_agent": ua})


def strip_meta(d: Optional[dict]):
    if not d:
        return None
    return {k: v for k, v in d.items() if k not in ("_id", "id", "created_at", "updated_at", "created_by", "created_by_name", "updated_by", "updated_by_name")}


def diff(before: dict, after: dict) -> dict:
    return {k: {"dari": before.get(k), "ke": after.get(k)} for k in after if k in strip_meta(after) and before.get(k) != after.get(k)}


async def notify_users(actor: dict, module: str, message: str):
    if module not in DATA_MODULES:
        return
    targets = await db.users.find({"notify.enabled": True, "notify.modules": module, "_id": {"$ne": ObjectId(actor["id"])}}).to_list(500)
    if not targets:
        return
    ts = datetime.now(timezone.utc).isoformat()
    await db.notifications.insert_many([{"user_id": str(t["_id"]), "module": module, "title": f"Data {MODULES[module]} baru",
                                         "message": message, "read": False, "ts": ts} for t in targets])


def stamp(d: dict, user: dict, created: bool):
    now = datetime.now(timezone.utc).isoformat()
    if created:
        d["created_at"] = now; d["created_by"] = user["id"]; d["created_by_name"] = user.get("name", "")
    else:
        d["updated_at"] = now; d["updated_by"] = user["id"]; d["updated_by_name"] = user.get("name", "")
    return d


def fmt_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d-%m-%Y %H:%M")
    except Exception:
        return iso


# ---------------------------------------------------------------------------
# Field definitions (sesuai kolom Excel DATA STOCK) & rumus
# ---------------------------------------------------------------------------
BASE_FIELDS = [("date", "Tanggal", False), ("lane", "Lane", False), ("type", "Type", False), ("ics_no", "ICS No.", False)]

FIELDS = {
    "smt_production": [("date", "TANGGAL", False), ("lane", "LANE", False), ("product", "PRODUCT", False),
        ("type", "TYPE", False), ("ics_no", "ICS NO", False), ("tt", "T/T", True), ("planing", "PLANING", True),
        ("act_s3", "ACT S3", True), ("act_s1", "ACT S1", True), ("act_s2", "ACT S2", True),
        ("plan_assy_s3", "PLAN ASSY S3", True), ("plan_assy_s1", "PLAN ASSY S1", True), ("plan_assy_s2", "PLAN ASSY S2", True)],
    "smt_stock": BASE_FIELDS + [
        ("stock_ok_prev", "Stock OK SMT Kemarin", True), ("coating", "Coating", True),
        ("belum_cutting", "Belum Cutting", True), ("belum_ict", "Belum ICT", True),
        ("belum_fct", "Belum FCT", True), ("ok", "OK", True), ("tray", "Tray", False)],
    "production_needs": BASE_FIELDS + [
        ("plan_assy", "Plan Assy Hari Ini", True), ("stock_ok_prev", "Stock OK SMT Kemarin", True)],
    "variance": BASE_FIELDS + [
        ("total_stock_prev", "Total Stock Kemarin", True), ("smt_total", "Total Produksi SMT", True),
        ("assy_total", "Total Produksi Assy", True), ("smt3", "SMT Shift 3", True),
        ("assy3", "Assy Shift 3", True), ("actual_total_stock", "Actual Total Stock", True),
        ("reason", "Keterangan", False)],
    "items": [("lane", "Lane", False), ("product", "Product", False), ("type", "Type", False), ("ics_no", "ICS No.", False),
              ("tt", "T/T (detik)", True), ("led_rank", "LED Rank", False), ("tray", "Tray", False)],
}


def compute_item(d: dict) -> dict:
    tt = num(d.get("tt"))
    d["cap_h"] = r1(3600 / tt) if tt else 0.0
    return d


def compute_smt_production(d: dict) -> dict:
    tt = num(d.get("tt"))
    d["cap_h"] = round(3600 / tt) if tt else 0.0
    d["total_smt"] = r1(num(d.get("act_s3")) + num(d.get("act_s1")) + num(d.get("act_s2")))
    planing = num(d.get("planing"))
    d["achv"] = round(d["total_smt"] / planing * 100, 1) if planing else 0.0
    d["total_plan"] = r1(num(d.get("plan_assy_s3")) + num(d.get("plan_assy_s1")) + num(d.get("plan_assy_s2")))
    d["balance"] = r1(d["total_smt"] - d["total_plan"])
    d["status"] = "SELESAI" if planing and d["total_smt"] >= planing else ("PROSES" if d["total_smt"] > 0 else "BELUM MULAI")
    return d


def compute_smt_stock(d: dict) -> dict:
    d["total"] = r1(num(d.get("coating")) + num(d.get("belum_cutting")) + num(d.get("belum_ict"))
                    + num(d.get("belum_fct")) + num(d.get("ok")))
    d["wip"] = r1(d["total"] - num(d.get("ok")))
    d["status"] = "OK" if num(d.get("ok")) > 0 else ("WIP" if d["total"] > 0 else "KOSONG")
    return d


def compute_needs(d: dict) -> dict:
    plan = num(d.get("plan_assy"))
    stock = num(d.get("stock_ok_prev"))
    d["blc"] = r1(stock - plan)
    d["fulfillment"] = round(stock / plan * 100, 1) if plan else 100.0
    d["status"] = "SHORTAGE" if d["blc"] < 0 else ("PAS" if d["blc"] == 0 else "CUKUP")
    return d


def compute_variance(d: dict) -> dict:
    x = num(d.get("actual_total_stock"))
    d["stok_jam"] = r1(x - num(d.get("smt3")) + num(d.get("assy3")))
    d["stock_sistem"] = r1(num(d.get("total_stock_prev")) + num(d.get("smt_total")) - num(d.get("assy_total")))
    d["variance"] = r1(x - d["stock_sistem"])
    d["variance_pct"] = round(d["variance"] / d["stock_sistem"] * 100, 2) if d["stock_sistem"] else 0.0
    d["variance_status"] = "OK" if d["variance"] == 0 else ("SURPLUS" if d["variance"] > 0 else "SHORTAGE")
    return d


DATASETS = {
    "smt-production": {"module": "smt_production", "compute": compute_smt_production, "sort": [("date", -1), ("lane", 1)]},
    "smt-stock": {"module": "smt_stock", "compute": compute_smt_stock, "sort": [("date", -1), ("lane", 1)]},
    "production-needs": {"module": "production_needs", "compute": compute_needs, "sort": [("date", -1), ("lane", 1)]},
    "variance": {"module": "variance", "compute": compute_variance, "sort": [("date", -1), ("lane", 1)]},
    "items": {"module": "items", "compute": compute_item, "sort": [("lane", 1), ("type", 1)], "no_date": True},
}


def normalize(module: str, body: dict) -> dict:
    d = {}
    for key, _label, is_num in FIELDS[module]:
        v = body.get(key)
        d[key] = num(v) if is_num else ("" if v is None or str(v) == "nan" else " ".join(str(v).split()))
    if d.get("ics_no", "").isdigit():
        d["ics_no"] = d["ics_no"].zfill(10)
    if module == "smt_stock" or module == "variance":
        d["reason"] = str(body.get("reason") or "")
    return DATASETS[[k for k, v in DATASETS.items() if v["module"] == module][0]]["compute"](d)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginBody(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    password: str
    name: str
    role: str
    permissions: Optional[Dict[str, str]] = None
    notify: Optional[dict] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    permissions: Optional[Dict[str, str]] = None
    notify: Optional[dict] = None


def validate_notify(n: Optional[dict]) -> dict:
    n = n or {}
    return {"enabled": bool(n.get("enabled")), "modules": [m for m in (n.get("modules") or []) if m in DATA_MODULES]}


def norm_username(u: str) -> str:
    u = (u or "").strip().lower()
    if len(u) < 3 or not all(c.isalnum() or c in "._-@" for c in u):
        raise HTTPException(status_code=400, detail="Username minimal 3 karakter (huruf, angka, titik, _ , -)")
    return u


def set_cookie(resp: Response, token: str):
    resp.set_cookie(key="access_token", value=token, httponly=True, secure=True,
                    samesite="none", max_age=604800, path="/")


@api.post("/auth/login")
async def login(body: LoginBody, response: Response):
    ident = body.username.strip().lower()
    user = await db.users.find_one({"$or": [{"username": ident}, {"email": ident}]})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Username atau password salah")
    token = create_access_token(str(user["_id"]), user.get("email") or ident)
    set_cookie(response, token)
    return {"token": token, "user": public_user(user)}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


def validate_perms(perms: Optional[Dict[str, str]]) -> Dict[str, str]:
    out = {}
    for m, lvl in (perms or {}).items():
        if m not in MODULES or lvl not in LEVELS:
            raise HTTPException(status_code=400, detail=f"Hak akses tidak valid: {m}={lvl}")
        out[m] = lvl
    return out


@api.get("/users")
async def list_users(user: dict = Depends(require_perm("users", "read"))):
    docs = await db.users.find({}).sort("created_at", -1).to_list(500)
    return [public_user(d) for d in docs]


@api.post("/users")
@api.post("/auth/register")
async def create_user(body: UserCreate, user: dict = Depends(require_perm("users", "write"))):
    username = norm_username(body.username)
    email = body.email.lower() if body.email else None
    if body.role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail="Role tidak valid")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
    if await db.users.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username sudah dipakai")
    if email and await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    doc = {"username": username, "password_hash": hash_password(body.password), "name": body.name.strip(),
           "role": body.role, "permissions": validate_perms(body.permissions), "notify": validate_notify(body.notify),
           "created_at": datetime.now(timezone.utc).isoformat()}
    if email:
        doc["email"] = email
    try:
        res = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Username atau email sudah dipakai")
    doc["_id"] = res.inserted_id
    return public_user(doc)


@api.put("/users/{uid}")
async def update_user(uid: str, body: UserUpdate, user: dict = Depends(require_perm("users", "write"))):
    target = await db.users.find_one({"_id": oid(uid)})
    if not target:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    is_main_admin = target.get("email") == os.environ.get("ADMIN_EMAIL", "").lower()
    upd = {}
    if body.username is not None:
        uname = norm_username(body.username)
        if await db.users.find_one({"username": uname, "_id": {"$ne": target["_id"]}}):
            raise HTTPException(status_code=400, detail="Username sudah dipakai")
        upd["username"] = uname
    if body.email is not None and not is_main_admin:
        em = body.email.lower()
        if await db.users.find_one({"email": em, "_id": {"$ne": target["_id"]}}):
            raise HTTPException(status_code=400, detail="Email sudah terdaftar")
        upd["email"] = em
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.role is not None:
        if body.role not in ROLE_LABELS:
            raise HTTPException(status_code=400, detail="Role tidak valid")
        if is_main_admin and body.role != "admin":
            raise HTTPException(status_code=400, detail="Role admin utama tidak dapat diubah")
        upd["role"] = body.role
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
        upd["password_hash"] = hash_password(body.password)
    if body.permissions is not None:
        upd["permissions"] = {} if is_main_admin else validate_perms(body.permissions)
    if body.notify is not None:
        upd["notify"] = validate_notify(body.notify)
    if upd:
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            await db.users.update_one({"_id": oid(uid)}, {"$set": upd})
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="Username atau email sudah dipakai")
    return public_user(await db.users.find_one({"_id": oid(uid)}))


@api.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_perm("users", "write"))):
    target = await db.users.find_one({"_id": oid(uid)})
    if not target:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if target.get("email") == os.environ.get("ADMIN_EMAIL", "").lower():
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun admin utama")
    if str(target["_id"]) == user["id"]:
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun sendiri")
    await db.users.delete_one({"_id": oid(uid)})
    return {"ok": True}


@api.get("/roles")
async def get_roles(user: dict = Depends(get_current_user)):
    return [{"value": k, "label": v, "defaults": ROLE_DEFAULT_PERMS[k]} for k, v in ROLE_LABELS.items()]


@api.get("/meta/modules")
async def get_modules(user: dict = Depends(get_current_user)):
    return {"modules": [{"key": k, "label": v} for k, v in MODULES.items()],
            "levels": [{"value": k, "label": LEVEL_LABELS[k]} for k in LEVELS]}


# ---------------------------------------------------------------------------
# Generic CRUD per dataset
# ---------------------------------------------------------------------------
def build_query(p: dict) -> dict:
    q = {}
    if p.get("date_from") or p.get("date_to"):
        rng = {}
        if p.get("date_from"):
            rng["$gte"] = p["date_from"]
        if p.get("date_to"):
            rng["$lte"] = p["date_to"]
        q["date"] = rng
    for k in ("lane", "type", "ics_no"):
        if p.get(k):
            q[k] = p[k]
    if p.get("search"):
        s = p["search"]
        q["$or"] = [{f: {"$regex": s, "$options": "i"}} for f in ("ics_no", "type", "lane")]
    return q


def register_crud(dataset: str):
    cfg = DATASETS[dataset]
    module = cfg["module"]
    coll = db[module]

    @api.get(f"/{dataset}")
    async def list_items(date_from: Optional[str] = None, date_to: Optional[str] = None,
                         lane: Optional[str] = None, type: Optional[str] = None, ics_no: Optional[str] = None,
                         status: Optional[str] = None, search: Optional[str] = None,
                         user: dict = Depends(require_perm(module, "read"))):
        q = build_query({"date_from": date_from, "date_to": date_to, "lane": lane, "type": type,
                         "ics_no": ics_no, "search": search})
        docs = await coll.find(q).sort(cfg["sort"]).to_list(5000)
        out = [clean(d) for d in docs]
        if status:
            out = [o for o in out if o.get("status") == status or o.get("variance_status") == status]
        return out

    @api.post(f"/{dataset}")
    async def create_item(body: dict, request: Request, user: dict = Depends(require_perm(module, "write"))):
        force = bool(body.get("force"))
        d = normalize(module, body)
        if not d.get("ics_no") or (not cfg.get("no_date") and not d.get("date")):
            raise HTTPException(status_code=400, detail="Tanggal dan ICS No. wajib diisi")
        key = {"ics_no": d["ics_no"], "type": d["type"]} if cfg.get("no_date") else {"date": d["date"], "ics_no": d["ics_no"], "type": d["type"]}
        existing = await coll.find_one(key)
        if existing and not force:
            when = f" pada {d['date']}" if d.get("date") else ""
            raise HTTPException(status_code=409, detail={
                "code": "DUPLICATE", "existing_id": str(existing["_id"]),
                "message": f"Data {d['ics_no']} ({d['type']}){when} sudah ada. Apakah Anda ingin memperbarui data yang ada atau membatalkan?"})
        if existing:
            before = clean(existing)
            stamp(d, user, False)
            await coll.update_one({"_id": existing["_id"]}, {"$set": d})
            doc = clean(await coll.find_one({"_id": existing["_id"]}))
            await log_audit(request, user, "UPDATE", module, doc["id"], before, doc, "Timpa data duplikat")
            return doc
        stamp(d, user, True)
        res = await coll.insert_one(d)
        d["id"] = str(res.inserted_id); d.pop("_id", None)
        await log_audit(request, user, "CREATE", module, d["id"], None, d)
        await notify_users(user, module, f"Data {MODULES[module]} baru ({d['ics_no']} · {d['type']}) telah diinput oleh {user['name']} pada {fmt_ts(d['created_at'])}. Silakan cek dashboard.")
        return d

    @api.put(f"/{dataset}/{{rid}}")
    async def update_item(rid: str, body: dict, request: Request, user: dict = Depends(require_perm(module, "write"))):
        existing = await coll.find_one({"_id": oid(rid)})
        if not existing:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        d = normalize(module, body)
        stamp(d, user, False)
        await coll.update_one({"_id": oid(rid)}, {"$set": d})
        doc = clean(await coll.find_one({"_id": oid(rid)}))
        await log_audit(request, user, "UPDATE", module, rid, clean(existing), doc)
        return doc

    @api.delete(f"/{dataset}/{{rid}}")
    async def delete_item(rid: str, request: Request, user: dict = Depends(require_perm(module, "write"))):
        existing = await coll.find_one({"_id": oid(rid)})
        await coll.delete_one({"_id": oid(rid)})
        if existing:
            await log_audit(request, user, "DELETE", module, rid, clean(existing), None)
        return {"ok": True}


for _ds in DATASETS:
    register_crud(_ds)


@api.get("/prev-values")
async def prev_values(date: str, ics_no: str, user: dict = Depends(get_current_user)):
    doc = await db.smt_stock.find({"ics_no": ics_no, "date": {"$lt": date}}).sort("date", -1).limit(1).to_list(1)
    if not doc:
        return {"found": False}
    d = doc[0]
    return {"found": True, "source_date": d["date"], "stock_ok_prev": num(d.get("ok")),
            "total_stock_prev": num(d.get("total"))}


# ---------------------------------------------------------------------------
# META options
# ---------------------------------------------------------------------------
@api.get("/meta/options")
async def meta_options(user: dict = Depends(get_current_user)):
    lanes, types, ics = set(), set(), set()
    for m in ("smt_production", "smt_stock", "production_needs", "variance"):
        lanes |= {x for x in await db[m].distinct("lane") if x}
        types |= {x for x in await db[m].distinct("type") if x}
        ics |= {x for x in await db[m].distinct("ics_no") if x}
    return {"lanes": sorted(lanes), "types": sorted(types), "ics_nos": sorted(ics),
            "stock_status": ["OK", "WIP", "KOSONG"],
            "lamp_status": ["SELESAI", "PROSES", "BELUM MULAI"],
            "needs_status": ["CUKUP", "PAS", "SHORTAGE"],
            "variance_status": ["OK", "SURPLUS", "SHORTAGE"]}


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@api.get("/dashboard/summary")
async def dashboard_summary(date_from: Optional[str] = None, date_to: Optional[str] = None,
                            user: dict = Depends(get_current_user)):
    dq = build_query({"date_from": date_from, "date_to": date_to})
    smt = await db.smt_production.find(dq).to_list(10000)
    needs = await db.production_needs.find(dq).to_list(10000)
    var = await db.variance.find(dq).to_list(10000)

    stock_dates = await db.smt_stock.distinct("date", dq)
    stock = await db.smt_stock.find({"date": max(stock_dates)}).to_list(10000) if stock_dates else []

    smt_total = sum(num(x.get("total_smt")) for x in smt)
    smt_plan = sum(num(x.get("planing")) for x in smt)
    plan_assy = sum(num(x.get("total_plan")) for x in smt)
    balance = smt_total - plan_assy
    stock_ok = sum(num(x.get("ok")) for x in stock)
    stock_total = sum(num(x.get("total")) for x in stock)
    shortage_items = [clean(n) for n in needs if n.get("status") == "SHORTAGE"]
    variance_items = [v for v in var if num(v.get("variance")) != 0]

    def trend(rows, keys):
        m = {}
        for x in rows:
            t = m.setdefault(x.get("date", ""), {"date": x.get("date", "")})
            for k, src in keys.items():
                t[k] = t.get(k, 0) + num(x.get(src))
        return sorted(m.values(), key=lambda r: r["date"])[-14:]

    by_lane = {}
    for x in smt:
        t = by_lane.setdefault(x.get("lane") or "-", {"lane": x.get("lane") or "-", "act_s3": 0, "act_s1": 0, "act_s2": 0})
        for s in ("act_s3", "act_s1", "act_s2"):
            t[s] += num(x.get(s))

    stock_breakdown = [
        {"name": "OK", "value": stock_ok},
        {"name": "Belum FCT", "value": sum(num(x.get("belum_fct")) for x in stock)},
        {"name": "Belum ICT", "value": sum(num(x.get("belum_ict")) for x in stock)},
        {"name": "Belum Cutting", "value": sum(num(x.get("belum_cutting")) for x in stock)},
        {"name": "Coating", "value": sum(num(x.get("coating")) for x in stock)},
    ]

    return {
        "kpi": {
            "smt_total": smt_total, "smt_items": len(smt), "smt_plan": smt_plan,
            "smt_achievement": round(smt_total / smt_plan * 100, 1) if smt_plan else 0.0,
            "plan_assy": plan_assy, "balance": balance,
            "stock_ok": stock_ok, "stock_total": stock_total, "stock_items": len(stock),
            "stock_date": max(stock_dates) if stock_dates else None,
            "shortage_count": len(shortage_items), "needs_items": len(needs),
            "variance_count": len(variance_items), "variance_items": len(var),
            "variance_sum": sum(num(v.get("variance")) for v in var),
        },
        "stock_breakdown": stock_breakdown,
        "smt_trend": trend(smt, {"plan": "planing", "actual": "total_smt", "plan_assy": "total_plan"}),
        "smt_by_lane": sorted(by_lane.values(), key=lambda r: r["lane"]),
        "top_shortage": sorted(shortage_items, key=lambda n: n["blc"])[:6],
        "top_variance": sorted([clean(v) for v in variance_items], key=lambda v: abs(num(v.get("variance"))), reverse=True)[:6],
    }


# ---------------------------------------------------------------------------
# EXCEL / CSV IMPORT + TEMPLATE
# ---------------------------------------------------------------------------
def header_map(module: str) -> Dict[str, str]:
    m = {}
    for key, label, _ in FIELDS[module]:
        m[key.lower()] = key
        m[label.lower()] = key
    m["part number"] = "ics_no"; m["part_number"] = "ics_no"; m["ics no."] = "ics_no"; m["ics no"] = "ics_no"
    m["tanggal"] = "date"; m["keterangan"] = "reason"; m["reason"] = "reason"
    for skip in ("cap/h", "total smt", "achv %", "total plan", "balance"):
        m[skip] = "__skip__"
    return m


def parse_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        dff = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    else:
        dff = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    dff = dff.dropna(how="all")
    return dff.astype(object).where(pd.notnull(dff), None)


def map_rows(module: str, dff: pd.DataFrame):
    hm = header_map(module)
    cols = {c: hm.get(str(c).strip().lower()) for c in dff.columns}
    unknown = [c for c, k in cols.items() if k is None]
    rows = []
    for rec in dff.to_dict(orient="records"):
        r = {}
        for c, k in cols.items():
            if k and k != "__skip__":
                r[k] = rec[c]
        if r.get("date"):
            try:
                r["date"] = pd.to_datetime(r["date"]).strftime("%Y-%m-%d")
            except Exception:
                pass
        if r.get("ics_no"):
            s = str(r["ics_no"]).strip()
            r["ics_no"] = s.split(".")[0].zfill(10) if s.replace(".", "").isdigit() else s
        rows.append(normalize(module, r))
    return rows, unknown


@api.get("/import/{dataset}/template")
async def import_template(dataset: str, user: dict = Depends(get_current_user)):
    if dataset not in DATASETS:
        raise HTTPException(status_code=400, detail="Dataset tidak dikenal")
    module = DATASETS[dataset]["module"]
    wb = Workbook(); ws = wb.active; ws.title = MODULES[module][:30]
    labels = [label for _, label, _ in FIELDS[module]]
    ws.append(labels)
    sample = await db[module].find_one({}) or {}
    ws.append([sample.get(k, "") if k != "date" else datetime.now().strftime("%Y-%m-%d") for k, _, _ in FIELDS[module]])
    for i, _ in enumerate(labels, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = 20
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="template_{dataset}.xlsx"'})


@api.post("/import/{dataset}/preview")
async def import_preview(dataset: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if dataset not in DATASETS:
        raise HTTPException(status_code=400, detail="Dataset tidak dikenal")
    module = DATASETS[dataset]["module"]
    try:
        dff = parse_dataframe(await file.read(), file.filename)
        rows, unknown = map_rows(module, dff)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {e}")
    invalid = sum(1 for r in rows if not r.get("ics_no") or (not DATASETS[dataset].get("no_date") and not r.get("date")))
    no_date = DATASETS[dataset].get("no_date")
    duplicates = 0
    for r in rows:
        if not r.get("ics_no"):
            continue
        key = {"ics_no": r["ics_no"], "type": r["type"]} if no_date else {"date": r.get("date"), "ics_no": r["ics_no"], "type": r["type"]}
        if await db[module].find_one(key):
            duplicates += 1; r["_duplicate"] = True
    columns = [k for k, _, _ in FIELDS[module]] + [k for k in rows[0].keys() if rows and k not in [f[0] for f in FIELDS[module]]] if rows else []
    return {"columns": columns, "rows": rows[:100], "total": len(rows), "invalid": invalid, "unknown_columns": unknown,
            "duplicates": duplicates, "new": len(rows) - invalid - duplicates}


@api.post("/import/{dataset}/confirm")
async def import_confirm(dataset: str, request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if dataset not in DATASETS:
        raise HTTPException(status_code=400, detail="Dataset tidak dikenal")
    module = DATASETS[dataset]["module"]
    if user["effective_permissions"].get(module) != "write":
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses import untuk data ini")
    try:
        dff = parse_dataframe(await file.read(), file.filename)
        rows, _ = map_rows(module, dff)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {e}")
    now = datetime.now(timezone.utc).isoformat()
    inserted = updated = skipped = 0
    no_date = DATASETS[dataset].get("no_date")
    for r in rows:
        if not r.get("ics_no") or (not no_date and not r.get("date")):
            skipped += 1
            continue
        key = {"ics_no": r["ics_no"], "type": r["type"]} if no_date else {"date": r["date"], "ics_no": r["ics_no"], "type": r["type"]}
        existing = await db[module].find_one(key)
        if existing:
            stamp(r, user, False)
            await db[module].update_one(key, {"$set": r}); updated += 1
            after = clean(await db[module].find_one({"_id": existing["_id"]}))
            await log_audit(request, user, "UPDATE", module, after["id"], clean(existing), after, f"Import {file.filename}")
        else:
            stamp(r, user, True)
            res = await db[module].insert_one(r); inserted += 1
            r["id"] = str(res.inserted_id); r.pop("_id", None)
            await log_audit(request, user, "CREATE", module, r["id"], None, r, f"Import {file.filename}")
    if inserted or updated:
        await notify_users(user, module, f"Import {MODULES[module]}: {inserted} data baru, {updated} diperbarui oleh {user['name']} pada {fmt_ts(now)}. Silakan cek dashboard.")
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


# ---------------------------------------------------------------------------
# AUDIT TRAIL & NOTIFICATIONS endpoints
# ---------------------------------------------------------------------------
@api.get("/audit")
async def list_audit(user_id: Optional[str] = None, action: Optional[str] = None, module: Optional[str] = None,
                     date_from: Optional[str] = None, date_to: Optional[str] = None, search: Optional[str] = None,
                     user: dict = Depends(require_perm("audit", "read"))):
    q = {}
    if user_id:
        q["user_id"] = user_id
    if action:
        q["action"] = action
    if module:
        q["module"] = module
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59.999999+00:00"
        q["ts"] = rng
    if search:
        q["$or"] = [{f: {"$regex": search, "$options": "i"}} for f in ("ics_no", "type", "user_name", "note")]
    docs = await db.audit_log.find(q).sort("ts", -1).to_list(500)
    return [clean(d) for d in docs]


@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    docs = await db.notifications.find({"user_id": user["id"]}).sort("ts", -1).to_list(100)
    unread = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"items": [clean(d) for d in docs], "unread": unread}


class ReadBody(BaseModel):
    ids: Optional[list] = None


@api.post("/notifications/read")
async def read_notifications(body: ReadBody, user: dict = Depends(get_current_user)):
    q = {"user_id": user["id"]}
    if body.ids:
        q["_id"] = {"$in": [oid(i) for i in body.ids]}
    await db.notifications.update_many(q, {"$set": {"read": True}})
    return {"ok": True}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup: indexes, admin seed, data seed dari DATA STOCK.xlsx
# ---------------------------------------------------------------------------
SEED_VERSION = 3


def read_csv_rows(path: Path):
    import csv
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


async def seed_from_excel():
    meta = await db.meta.find_one({"_id": "seed"})
    if meta and meta.get("version") == SEED_VERSION:
        return
    now = datetime.now(timezone.utc).isoformat()
    if not meta or meta.get("version", 0) < 2:
        path = ROOT_DIR / "seed" / "data_stock.json"
        if path.exists():
            rows = json.loads(path.read_text())
            prod_date, stock_date = "2026-09-12", "2026-09-13"
            payload = {"smt_stock": [], "production_needs": [], "variance": []}
            for r in rows:
                base = {"lane": r["lane"], "type": r["type"], "ics_no": r["ics_no"]}
                stock = normalize("smt_stock", {**base, "date": stock_date, "stock_ok_prev": r["stock_ok_prev"], "coating": r["coating"],
                                                "belum_cutting": r["belum_cutting"], "belum_ict": r["belum_ict"],
                                                "belum_fct": r["belum_fct"], "ok": r["ok"], "tray": r["tray"]})
                needs = normalize("production_needs", {**base, "date": prod_date, "plan_assy": r["plan_assy"], "stock_ok_prev": r["stock_ok_prev"]})
                smt_total = r["smt1"] + r["smt2"] + r["smt3"]
                assy_total = r["assy1"] + r["assy2"] + r["assy3"]
                var = normalize("variance", {**base, "date": stock_date, "total_stock_prev": r["total_stock_prev"],
                                             "smt_total": smt_total, "assy_total": assy_total, "smt3": r["smt3"],
                                             "assy3": r["assy3"], "actual_total_stock": stock["total"]})
                for m, d in (("smt_stock", stock), ("production_needs", needs), ("variance", var)):
                    d["created_at"] = now
                    payload[m].append(d)
            for m, docs in payload.items():
                await db[m].delete_many({})
                if docs:
                    await db[m].insert_many(docs)
                await db[m].create_index([("date", -1), ("ics_no", 1)])
    # v3: gabung Produksi SMT & ASSY sesuai format CSV
    csv_path = ROOT_DIR / "seed" / "smt_production.csv"
    if csv_path.exists():
        hm = header_map("smt_production")
        docs = []
        for rec in read_csv_rows(csv_path):
            r = {hm.get(k.strip().lower()): v for k, v in rec.items() if hm.get(k.strip().lower()) not in (None, "__skip__")}
            r["date"] = pd.to_datetime(r["date"]).strftime("%Y-%m-%d")
            d = normalize("smt_production", r)
            d["created_at"] = now
            docs.append(d)
        await db.smt_production.delete_many({})
        if docs:
            await db.smt_production.insert_many(docs)
        await db.smt_production.create_index([("date", -1), ("ics_no", 1)])
        for rec in read_csv_rows(csv_path):
            await db.items.update_many({"ics_no": rec["ICS NO"].strip()},
                                       {"$set": {"product": rec["PRODUCT"].strip(), "tt": num(rec["T/T"]),
                                                 "cap_h": round(3600 / num(rec["T/T"])) if num(rec["T/T"]) else 0.0}})
        await db.items.update_many({"product": {"$exists": False}}, {"$set": {"product": "REGULER"}})
    await db.lamp_production.drop()
    await db.meta.update_one({"_id": "seed"}, {"$set": {"version": SEED_VERSION, "at": now}}, upsert=True)
    logger.info("Seed v%d applied", SEED_VERSION)


async def seed_admin():
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({"username": os.environ.get("ADMIN_USERNAME", "admin"), "email": email,
                                   "password_hash": hash_password(password),
                                   "name": "Admin Utama", "role": "admin", "permissions": {},
                                   "created_at": datetime.now(timezone.utc).isoformat()})
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})
    if existing is not None and not existing.get("username"):
        await db.users.update_one({"email": email}, {"$set": {"username": os.environ.get("ADMIN_USERNAME", "admin")}})


async def seed_demo_users():
    demos = [
        ("ppic@cds.co.id", "PPIC Andi", "production_planning"),
        ("pc@cds.co.id", "PC Budi", "production_control"),
        ("smt@cds.co.id", "SMT Citra", "smt"),
        ("assy@cds.co.id", "Assy Dewi", "assembly"),
        ("manager@cds.co.id", "Manager Eko", "management"),
    ]
    for email, name, role in demos:
        uname = email.split("@")[0]
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({"username": uname, "email": email, "password_hash": hash_password("password123"),
                                       "name": name, "role": role, "permissions": {},
                                       "created_at": datetime.now(timezone.utc).isoformat()})
    async for u in db.users.find({"username": {"$exists": False}}):
        await db.users.update_one({"_id": u["_id"]}, {"$set": {"username": (u.get("email") or str(u["_id"])).split("@")[0]}})



async def seed_items():
    if await db.items.count_documents({}) > 0:
        return
    path = ROOT_DIR / "seed" / "data_stock.json"
    if not path.exists():
        return
    seen, docs = set(), []
    now = datetime.now(timezone.utc).isoformat()
    for r in json.loads(path.read_text()):
        key = (r["ics_no"], r["type"])
        if key in seen or not r["ics_no"].strip("0"):
            continue
        seen.add(key)
        d = normalize("items", r)
        d["created_at"] = now
        docs.append(d)
    await db.items.insert_many(docs)
    await db.items.create_index([("ics_no", 1), ("type", 1)])
    logger.info("Seeded %d master items", len(docs))


@app.on_event("startup")
async def startup():
    try:
        await db.users.drop_index("email_1")
    except Exception:
        pass
    await db.users.update_many({"email": None}, {"$unset": {"email": ""}})
    await db.users.create_index("email", unique=True,
                                partialFilterExpression={"email": {"$type": "string"}})
    await db.users.create_index("username", unique=True, sparse=True)
    await db.audit_log.create_index([("ts", -1)])
    await db.notifications.create_index([("user_id", 1), ("read", 1), ("ts", -1)])
    await seed_admin()
    await seed_demo_users()
    await seed_from_excel()
    await seed_items()


@app.on_event("shutdown")
async def shutdown():
    client.close()
