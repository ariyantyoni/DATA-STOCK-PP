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
import zipfile
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
    "smt": "Part Production",
    "assembly": "Assembly (LAMP ASSY)",
}

MODULES = {
    "smt_production": "Produksi Part & ASSY",
    "smt_stock": "Stock Part",
    "production_needs": "Kebutuhan Assy VS. Stock Part",
    "variance": "Variance Stock",
    "items": "Master Item",
    "stock_standards": "Standar Stock",
    "audit": "Audit Trail",
    "backup": "Backup & Restore",
    "users": "Manajemen User",
}
LEVELS = ["none", "read", "write"]
LEVEL_LABELS = {"none": "Tidak ada", "read": "Lihat", "write": "Ubah"}

ROLE_DEFAULT_PERMS = {
    "admin": {m: "write" for m in MODULES},
    "management": {**{m: "write" for m in MODULES}, "users": "none", "audit": "read", "backup": "none"},
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
    base.setdefault("backup", "none")
    base.setdefault("stock_standards", base.get("items", "none"))
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
DATA_MODULES = ["smt_production", "smt_stock", "production_needs", "variance", "items", "stock_standards"]


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
        ("type", "TYPE", False), ("ics_no", "ICS NO", False), ("tt", "T/T", True), ("planing_smt", "PLANING PART", True),
        ("act_smt_s3", "ACT PART S3", True), ("act_smt_s1", "ACT PART S1", True), ("act_smt_s2", "ACT PART S2", True),
        ("plan_assy", "PLAN ASSY", True),
        ("act_assy_s3", "ACT ASSY S3", True), ("act_assy_s1", "ACT ASSY S1", True), ("act_assy_s2", "ACT ASSY S2", True)],
    "smt_stock": [("date", "Tanggal", False), ("lane", "Lane", False), ("product", "Product", False), ("type", "Type", False), ("ics_no", "ICS No.", False)] + [
        ("stock_ok_prev", "Stock OK Part Kemarin", True), ("coating", "Coating", True),
        ("belum_cutting", "Belum Cutting", True), ("belum_ict", "Belum ICT", True),
        ("belum_fct", "Belum FCT", True), ("ok", "OK", True)],
    "production_needs": BASE_FIELDS + [
        ("plan_assy", "Plan Assy Hari Ini", True), ("stock_ok_prev", "Stock OK Part Kemarin", True)],
    "variance": BASE_FIELDS + [
        ("total_stock_prev", "Total Stock Kemarin", True), ("smt_total", "Total Produksi Part", True),
        ("assy_total", "Total Produksi Assy", True), ("smt3", "Part Shift 3", True),
        ("assy3", "Assy Shift 3", True), ("actual_total_stock", "Actual Total Stock", True),
        ("reason", "Keterangan", False)],
    "items": [("lane", "Lane", False), ("product", "Product", False), ("type", "Type", False), ("ics_no", "ICS No.", False),
              ("tt", "T/T (detik)", True), ("tt_assy", "T/T Assy (detik/unit)", True), ("material_per_unit", "Kebutuhan Material per Unit Assy", True),
              ("proses_mesin", "PROSES MESIN", False)],
    "stock_standards": [("lane", "Lane", False), ("product", "Product", False), ("type", "Type", False), ("standard_stock", "Standart Stock", True)],
}


def compute_standard(d: dict) -> dict:
    return d


def compute_item(d: dict) -> dict:
    tt = num(d.get("tt"))
    d["cap_h"] = r1(3600 / tt) if tt else 0.0
    return d


def compute_smt_production(d: dict) -> dict:
    tt = num(d.get("tt"))
    d["cap_h"] = round(3600 / tt) if tt else 0.0
    d["total_act_smt"] = r1(num(d.get("act_smt_s3")) + num(d.get("act_smt_s1")) + num(d.get("act_smt_s2")))
    planing = num(d.get("planing_smt"))
    d["achv"] = round(d["total_act_smt"] / planing * 100, 1) if planing else 0.0
    d["total_act_assy"] = r1(num(d.get("act_assy_s3")) + num(d.get("act_assy_s1")) + num(d.get("act_assy_s2")))
    d["balance"] = r1(d["total_act_smt"] - d["total_act_assy"])
    d["status"] = "SELESAI" if planing and d["total_act_smt"] >= planing else ("PROSES" if d["total_act_smt"] > 0 else "BELUM MULAI")
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
    "stock-standards": {"module": "stock_standards", "compute": compute_standard, "sort": [("lane", 1), ("product", 1), ("type", 1)], "no_date": True, "key": ["lane", "product", "type"]},
}


def normalize(module: str, body: dict) -> dict:
    d = {}
    for key, _label, is_num in FIELDS[module]:
        v = body.get(key)
        d[key] = num(v) if is_num else ("" if v is None or str(v) == "nan" else " ".join(str(v).split()))
    if d.get("ics_no", "").isdigit():
        d["ics_no"] = d["ics_no"].zfill(10)
    if module == "items":
        d["material_per_unit"] = num(body.get("material_per_unit"), 1.0) or 1.0
    if module == "smt_stock":
        d["stock_ok_manual"] = bool(body.get("stock_ok_manual"))
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
    for k in ("lane", "type", "ics_no", "product"):
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
                         product: Optional[str] = None,
                         status: Optional[str] = None, search: Optional[str] = None,
                         user: dict = Depends(require_perm(module, "read"))):
        p = {"date_from": date_from, "date_to": date_to, "lane": lane, "type": type, "ics_no": ics_no, "search": search}
        if module == "production_needs":
            out = await needs_view(p, product)
        elif module == "variance":
            out = await variance_view(p, product)
        else:
            docs = await coll.find(build_query(p)).sort(cfg["sort"]).to_list(5000)
            out = [clean(d) for d in docs]
            if module == "smt_stock":
                out = await enrich_stock(out)
            if product:
                out = [o for o in out if o.get("product") == product]
        if status:
            out = [o for o in out if o.get("status") == status or o.get("variance_status") == status or o.get("indikator") == status]
        return out

    @api.post(f"/{dataset}")
    async def create_item(body: dict, request: Request, user: dict = Depends(require_perm(module, "write"))):
        force = bool(body.get("force"))
        d = normalize(module, body)
        if not cfg.get("key") and (not d.get("ics_no") or (not cfg.get("no_date") and not d.get("date"))):
            raise HTTPException(status_code=400, detail="Tanggal dan ICS No. wajib diisi")
        if cfg.get("key"):
            key = {k: d.get(k, "") for k in cfg["key"]}
            if not all(key.values()):
                raise HTTPException(status_code=400, detail="Lane, Product dan Type wajib diisi")
        elif cfg.get("no_date"):
            key = {"ics_no": d["ics_no"], "type": d["type"]}
        else:
            key = {"date": d["date"], "ics_no": d["ics_no"], "type": d["type"]}
        existing = await coll.find_one(key)
        if existing and not force:
            when = f" pada {d['date']}" if d.get("date") else ""
            raise HTTPException(status_code=409, detail={
                "code": "DUPLICATE", "existing_id": str(existing["_id"]),
                "message": f"Data {d.get('ics_no') or d.get('product')} ({d.get('type') or d.get('lane')}){when} sudah ada. Apakah Anda ingin memperbarui data yang ada atau membatalkan?"})
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
        await notify_users(user, module, f"Data {MODULES[module]} baru ({d.get('ics_no') or d.get('product')} · {d.get('type') or d.get('lane')}) telah diinput oleh {user['name']} pada {fmt_ts(d['created_at'])}. Silakan cek dashboard.")
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


async def prev_stock(date: str, ics_no: str, type_: Optional[str] = None):
    q = {"ics_no": ics_no}
    if type_:
        q["type"] = type_
    try:
        h1 = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        return None
    doc = await db.smt_stock.find_one({**q, "date": h1})
    if not doc:
        docs = await db.smt_stock.find({**q, "date": {"$lt": date}}).sort("date", -1).limit(1).to_list(1)
        doc = docs[0] if docs else None
    if not doc and type_:
        return await prev_stock(date, ics_no, None)
    return doc


@api.get("/prev-values")
async def prev_values(date: str, ics_no: str, type: Optional[str] = None, user: dict = Depends(get_current_user)):
    d = await prev_stock(date, ics_no, type)
    if not d:
        return {"found": False}
    return {"found": True, "source_date": d["date"], "stock_ok_prev": num(d.get("ok")),
            "total_stock_prev": num(d.get("total"))}


async def link_stock_prev(docs: list) -> list:
    """Isi stock_ok_prev dari Stock SMT H-1 untuk dokumen smt_stock yang tidak diedit manual."""
    for d in docs:
        if d.get("stock_ok_manual"):
            continue
        p = await prev_stock(d.get("date", ""), d.get("ics_no", ""), d.get("type"))
        if p:
            d["stock_ok_prev"] = num(p.get("ok")); d["stock_ok_prev_source"] = p["date"]
    return docs


# ---------------------------------------------------------------------------
# Integrasi antar-modul (PRODUCT mapping, standar stock, view Kebutuhan & Variance)
# ---------------------------------------------------------------------------
async def product_map() -> dict:
    m = {}
    for it in await db.items.find({}, {"ics_no": 1, "type": 1, "product": 1, "tt_assy": 1, "material_per_unit": 1}).to_list(10000):
        m[(it.get("ics_no"), it.get("type"))] = it
        m.setdefault((it.get("ics_no"), None), it)
    return m


def item_of(pm: dict, ics: str, typ: str):
    return pm.get((ics, typ)) or pm.get((ics, None)) or {}


def fill_product(doc: dict, pm: dict) -> dict:
    if not doc.get("product"):
        doc["product"] = item_of(pm, doc.get("ics_no"), doc.get("type")).get("product") or ""
    return doc


async def standards_map() -> dict:
    return {(s.get("lane"), s.get("product"), s.get("type")): num(s.get("standard_stock")) for s in await db.stock_standards.find({}).to_list(5000)}


def indikator(total, std):
    if std is None:
        return "BELUM DISET"
    if total is None:
        return "BELUM DICEK"
    return "PASS" if total == std else ("MINUS" if total < std else "OVER")


async def enrich_stock(docs: list) -> list:
    pm, sm = await product_map(), await standards_map()
    docs = await link_stock_prev(docs)
    dates = sorted({d.get("date") for d in docs if d.get("date")})
    prods = await db.smt_production.find({"date": {"$in": dates}}, {"date": 1, "ics_no": 1, "type": 1, "planing_smt": 1}).to_list(20000) if dates else []
    plan = {}
    for x in prods:
        on = num(x.get("planing_smt")) > 0
        plan[(x["date"], x.get("ics_no"), x.get("type"))] = plan.get((x["date"], x.get("ics_no"), x.get("type")), False) or on
        plan[(x["date"], x.get("ics_no"), None)] = plan.get((x["date"], x.get("ics_no"), None), False) or on
    for d in docs:
        fill_product(d, pm)
        std = sm.get((d.get("lane"), d.get("product"), d.get("type")))
        d["standard_stock"] = std
        d["indikator"] = indikator(num(d.get("total")), std)
        k = (d.get("date"), d.get("ics_no"), d.get("type"))
        on = plan.get(k) if k in plan else plan.get((d.get("date"), d.get("ics_no"), None), False)
        d["kondisi_produksi"] = "ON" if on else "OFF"
    return docs


async def needs_view(p: dict, product: Optional[str]) -> list:
    prods = await db.smt_production.find(build_query(p)).sort([("date", -1), ("lane", 1)]).to_list(5000)
    dates = sorted({x["date"] for x in prods})
    stocks = await db.smt_stock.find({"date": {"$in": dates}}).to_list(10000) if dates else []
    sm = {(s["date"], s.get("ics_no"), s.get("type")): s for s in stocks}
    sm_ics = {}
    for s in stocks:
        sm_ics.setdefault((s["date"], s.get("ics_no")), s)
    pm = await product_map()
    out = []
    for x in prods:
        r = fill_product(clean(x), pm)
        if product and r.get("product") != product:
            continue
        it = item_of(pm, r.get("ics_no"), r.get("type"))
        st = sm.get((r["date"], r.get("ics_no"), r.get("type"))) or sm_ics.get((r["date"], r.get("ics_no")))
        stock = num(st.get("total")) if st else 0.0
        planing, plan_assy = num(r.get("planing_smt")), num(r.get("plan_assy"))
        tt_assy = num(it.get("tt_assy")) or None
        mpu = num(it.get("material_per_unit"), 1.0) or 1.0
        active = planing > 0 or plan_assy > 0
        if not active or not tt_assy:
            ws = None
        else:
            ws = 0.0 if stock <= 0 else round(stock / mpu * tt_assy / 3600, 2)
        blc = r1(stock - plan_assy)
        out.append({
            "id": r["id"], "date": r["date"], "lane": r.get("lane"), "product": r.get("product"), "type": r.get("type"),
            "ics_no": r.get("ics_no"), "planing_smt": planing, "kondisi_produksi": "ON" if planing > 0 else "OFF",
            "plan_assy": plan_assy, "stock_ok_today": stock, "stock_id": str(st["_id"]) if st else None, "has_stock": bool(st),
            "tt_assy": tt_assy, "material_per_unit": mpu, "waktu_shortage": ws, "blc": blc,
            "fulfillment": round(stock / plan_assy * 100, 1) if plan_assy else 100.0,
            "status": "SHORTAGE" if blc < 0 else ("PAS" if blc == 0 else "CUKUP"),
        })
    return out


async def variance_view(p: dict, product: Optional[str]) -> list:
    stocks = await db.smt_stock.find(build_query(p)).sort([("date", -1), ("lane", 1)]).to_list(5000)
    all_stock = await db.smt_stock.find({}, {"date": 1, "ics_no": 1, "type": 1, "total": 1}).to_list(20000)
    hist = {}
    for s in all_stock:
        hist.setdefault((s.get("ics_no"), s.get("type")), []).append((s["date"], num(s.get("total"))))
    dates = sorted({x["date"] for x in stocks})
    prods = await db.smt_production.find({"date": {"$in": dates}}).to_list(10000) if dates else []
    pmap = {(x["date"], x.get("ics_no"), x.get("type")): x for x in prods}
    pmap_ics = {}
    for x in prods:
        pmap_ics.setdefault((x["date"], x.get("ics_no")), x)
    pm = await product_map()
    out = []
    for s in stocks:
        r = fill_product(clean(s), pm)
        if product and r.get("product") != product:
            continue
        prev = [t for d, t in hist.get((r.get("ics_no"), r.get("type")), []) if d < r["date"]]
        prev_total = None
        if prev:
            prev_total = max(((d, t) for d, t in hist[(r.get("ics_no"), r.get("type"))] if d < r["date"]), key=lambda z: z[0])[1]
        pr = pmap.get((r["date"], r.get("ics_no"), r.get("type"))) or pmap_ics.get((r["date"], r.get("ics_no")))
        smt_total = num(pr.get("total_act_smt")) if pr else 0.0
        assy_total = num(pr.get("total_act_assy")) if pr else 0.0
        actual = num(r.get("total"))
        if prev_total is None:
            sistem = var = pct = None; status = "BELUM DICEK"
        else:
            sistem = r1(prev_total + smt_total - assy_total); var = r1(actual - sistem)
            pct = round(var / sistem * 100, 2) if sistem else 0.0
            status = "OK" if var == 0 else ("VARIANCE -" if var < 0 else "VARIANCE +")
        out.append({
            "id": r["id"], "date": r["date"], "lane": r.get("lane"), "product": r.get("product"), "type": r.get("type"),
            "ics_no": r.get("ics_no"), "total_stock_prev": prev_total, "smt_total": smt_total, "assy_total": assy_total,
            "has_production": bool(pr), "actual_total_stock": actual, "stock_sistem": sistem, "variance": var,
            "variance_pct": pct, "variance_status": status,
        })
    return out


# ---------------------------------------------------------------------------
# META options
# ---------------------------------------------------------------------------
@api.get("/meta/options")
async def meta_options(user: dict = Depends(get_current_user)):
    lanes, types, ics = set(), set(), set()
    # Sumber utama: Master Item (agar semua modul di dashboard terhubung ke master),
    # digabung dengan nilai yang sudah ada di data transaksi.
    for m in ("items", "smt_production", "smt_stock", "production_needs", "variance"):
        lanes |= {x for x in await db[m].distinct("lane") if x}
        types |= {x for x in await db[m].distinct("type") if x}
        ics |= {x for x in await db[m].distinct("ics_no") if x}
    return {"lanes": sorted(lanes), "types": sorted(types), "ics_nos": sorted(ics),
            "products": sorted({x for x in await db.items.distinct("product") if x} | {x for x in await db.smt_production.distinct("product") if x}),
            "stock_status": ["OK", "WIP", "KOSONG"],
            "indikator": ["PASS", "MINUS", "OVER", "BELUM DISET"],
            "lamp_status": ["SELESAI", "PROSES", "BELUM MULAI"],
            "needs_status": ["CUKUP", "PAS", "SHORTAGE", "BELUM DICEK"],
            "variance_status": ["OK", "VARIANCE +", "VARIANCE -", "BELUM DICEK"]}


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@api.get("/dashboard/summary")
async def dashboard_summary(date_from: Optional[str] = None, date_to: Optional[str] = None, product: Optional[str] = None,
                            user: dict = Depends(get_current_user)):
    dq = build_query({"date_from": date_from, "date_to": date_to})
    p = {"date_from": date_from, "date_to": date_to}
    smt = await db.smt_production.find(dq).to_list(10000)
    needs = await needs_view(p, product)
    var = await variance_view(p, product)

    stock_dates = await db.smt_stock.distinct("date", dq)
    stock = await enrich_stock([clean(s) for s in await db.smt_stock.find({"date": max(stock_dates)}).to_list(10000)]) if stock_dates else []
    if product:
        pm = await product_map()
        smt = [x for x in smt if fill_product(x, pm).get("product") == product]
        stock = [x for x in stock if x.get("product") == product]

    smt_total = sum(num(x.get("total_act_smt")) for x in smt)
    smt_plan = sum(num(x.get("planing_smt")) for x in smt)
    plan_assy = sum(num(x.get("plan_assy")) for x in smt)
    assy_total = sum(num(x.get("total_act_assy")) for x in smt)
    balance = smt_total - assy_total
    stock_ok = sum(num(x.get("ok")) for x in stock)
    stock_total = sum(num(x.get("total")) for x in stock)
    shortage_items = [n for n in needs if n.get("status") == "SHORTAGE"]
    variance_items = [v for v in var if v.get("variance") not in (None, 0)]

    def trend(rows, keys):
        m = {}
        for x in rows:
            t = m.setdefault(x.get("date", ""), {"date": x.get("date", "")})
            for k, src in keys.items():
                t[k] = t.get(k, 0) + num(x.get(src))
        return sorted(m.values(), key=lambda r: r["date"])[-14:]

    by_lane = {}
    for x in smt:
        t = by_lane.setdefault(x.get("lane") or "-", {"lane": x.get("lane") or "-", "act_smt_s3": 0, "act_smt_s1": 0, "act_smt_s2": 0})
        for s in ("act_smt_s3", "act_smt_s1", "act_smt_s2"):
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
            "plan_assy": plan_assy, "assy_total": assy_total, "balance": balance,
            "assy_achievement": round(assy_total / plan_assy * 100, 1) if plan_assy else 0.0,
            "stock_ok": stock_ok, "stock_total": stock_total, "stock_items": len(stock),
            "stock_date": max(stock_dates) if stock_dates else None,
            "shortage_count": len(shortage_items), "needs_items": len(needs),
            "variance_count": len(variance_items), "variance_items": len(var),
            "variance_sum": sum(num(v.get("variance")) for v in var),
        },
        "stock_breakdown": stock_breakdown,
        "smt_trend": trend(smt, {"plan": "planing_smt", "actual": "total_act_smt", "plan_assy": "plan_assy", "actual_assy": "total_act_assy"}),
        "smt_by_lane": sorted(by_lane.values(), key=lambda r: r["lane"]),
        "top_shortage": sorted(shortage_items, key=lambda n: n["blc"])[:6],
        "top_variance": sorted(variance_items, key=lambda v: abs(num(v.get("variance"))), reverse=True)[:6],
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
    # Alias tambahan agar file lampiran & hasil export tetap terbaca (variasi penulisan label kolom)
    m["t/t assy (dtk/unit)"] = "tt_assy"; m["t/t assy (detik/unit)"] = "tt_assy"; m["t/t assy"] = "tt_assy"
    m["material / unit assy"] = "material_per_unit"; m["material/unit assy"] = "material_per_unit"
    m["standart stock"] = "standard_stock"; m["standar stock"] = "standard_stock"
    m["proses mesin"] = "proses_mesin"
    for skip in ("cap/h", "total smt", "achv %", "total plan", "balance", "total act smt", "total act assy"):
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


def import_row_valid(dataset: str, r: dict) -> bool:
    """Baris dianggap valid jika field kunci dataset lengkap.
    - dataset dengan 'key' (mis. stock-standards: lane+product+type) → cek key tsb, TIDAK butuh ics_no.
    - dataset lain → butuh ics_no, dan butuh date kecuali no_date.
    """
    ck = DATASETS[dataset].get("key")
    if ck:
        return all(str(r.get(k) or "").strip() for k in ck)
    if not (str(r.get("ics_no") or "").strip()):
        return False
    if not DATASETS[dataset].get("no_date") and not r.get("date"):
        return False
    return True


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
    invalid = sum(1 for r in rows if not import_row_valid(dataset, r))
    no_date = DATASETS[dataset].get("no_date")
    duplicates = 0
    for r in rows:
        if not r.get("ics_no") and not DATASETS[dataset].get("key"):
            continue
        ck = DATASETS[dataset].get("key")
        key = {k: r.get(k, "") for k in ck} if ck else ({"ics_no": r["ics_no"], "type": r["type"]} if no_date else {"date": r.get("date"), "ics_no": r["ics_no"], "type": r["type"]})
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
        ck = DATASETS[dataset].get("key")
        if ck:
            if not all(r.get(k) for k in ck):
                skipped += 1
                continue
            key = {k: r.get(k) for k in ck}
        elif not r.get("ics_no") or (not no_date and not r.get("date")):
            skipped += 1
            continue
        else:
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


# ---------------------------------------------------------------------------
# BACKUP & RESTORE (.zip berisi JSON per modul)
# ---------------------------------------------------------------------------
BACKUP_COLLECTIONS = DATA_MODULES + ["users", "audit_log", "notifications"]
RESTORE_COLLECTIONS = DATA_MODULES


def to_jsonable(doc: dict) -> dict:
    d = dict(doc)
    d["_id"] = str(d["_id"])
    return d


@api.get("/backup/export")
async def backup_export(user: dict = Depends(require_perm("backup", "write"))):
    buf = io.BytesIO()
    counts = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in BACKUP_COLLECTIONS:
            docs = [to_jsonable(d) for d in await db[c].find({}).to_list(100000)]
            counts[c] = len(docs)
            zf.writestr(f"{c}.json", json.dumps(docs, ensure_ascii=False, default=str))
        zf.writestr("meta.json", json.dumps({"app": "Control Data Stock & Production", "version": 1,
                                             "exported_at": datetime.now(timezone.utc).isoformat(),
                                             "exported_by": user["name"], "counts": counts,
                                             "modules": {c: MODULES.get(c, c) for c in BACKUP_COLLECTIONS}}, ensure_ascii=False))
    buf.seek(0)
    await log_audit(None, user, "BACKUP", "backup", note=f"Export {sum(counts.values())} dokumen")
    fname = f"backup_cds_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(buf, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def read_backup(file_bytes: bytes, filename: str):
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File backup harus berformat .zip (hasil export aplikasi ini)")
    try:
        zf = zipfile.ZipFile(io.BytesIO(file_bytes))
        names = set(zf.namelist())
        if "meta.json" not in names:
            raise ValueError("meta.json tidak ditemukan")
        meta = json.loads(zf.read("meta.json"))
        data = {c: json.loads(zf.read(f"{c}.json")) for c in RESTORE_COLLECTIONS if f"{c}.json" in names}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File backup tidak valid: {e}")
    if not data:
        raise HTTPException(status_code=400, detail="Tidak ada data modul di dalam file backup")
    return meta, data


@api.post("/backup/preview")
async def backup_preview(file: UploadFile = File(...), user: dict = Depends(require_perm("backup", "write"))):
    meta, data = read_backup(await file.read(), file.filename)
    current = {c: await db[c].count_documents({}) for c in data}
    return {"meta": meta, "modules": [{"key": c, "label": MODULES.get(c, c), "in_backup": len(v), "current": current[c]} for c, v in data.items()]}


@api.post("/backup/restore")
async def backup_restore(request: Request, file: UploadFile = File(...), user: dict = Depends(require_perm("backup", "write"))):
    meta, data = read_backup(await file.read(), file.filename)
    result = {}
    for c, docs in data.items():
        for d in docs:
            try:
                d["_id"] = ObjectId(d["_id"])
            except Exception:
                d.pop("_id", None)
        removed = (await db[c].delete_many({})).deleted_count
        if docs:
            await db[c].insert_many(docs)
        result[c] = {"removed": removed, "restored": len(docs)}
        await log_audit(request, user, "RESTORE", c, note=f"Restore dari {file.filename} ({meta.get('exported_at', '')[:19]}): {removed} dihapus, {len(docs)} dipulihkan")
    return {"ok": True, "result": result}


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
SEED_VERSION = 4


def read_csv_rows(path: Path):
    import csv
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


async def seed_from_excel():
    meta = await db.meta.find_one({"_id": "seed"})
    if meta and meta.get("version") == SEED_VERSION:
        return
    now = datetime.now(timezone.utc).isoformat()
    # PART PRODUCTION: aplikasi baru dimulai dengan DATA TRANSAKSI KOSONG & independen
    # dari aplikasi SMT. Tidak ada data smt_production / smt_stock / production_needs /
    # variance yang di-seed. Hanya master item yang di-seed (lihat seed_items()).
    await db.lamp_production.drop()
    await db.meta.update_one({"_id": "seed"}, {"$set": {"version": SEED_VERSION, "at": now}}, upsert=True)
    logger.info("Seed v%d applied (Part Production - transaksi kosong)", SEED_VERSION)


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
        ("smt@cds.co.id", "Part Citra", "smt"),
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



ITEMS_SEED_VERSION = 1


async def seed_items():
    # Master Item bersumber dari seed/items.csv (sesuai lampiran). Idempotent via marker
    # 'items_seed' sehingga hanya reseed saat versi berubah — item tambahan user tidak terhapus di restart biasa.
    marker = await db.meta.find_one({"_id": "items_seed"})
    if marker and marker.get("version") == ITEMS_SEED_VERSION:
        return
    csv_path = ROOT_DIR / "seed" / "items.csv"
    if not csv_path.exists():
        return
    hmap = {"lane": "lane", "product": "product", "type": "type", "ics no.": "ics_no",
            "ics no": "ics_no", "t/t (detik)": "tt", "cap/h": "cap_h",
            "t/t assy (dtk/unit)": "tt_assy", "proses mesin": "proses_mesin",
            "material / unit assy": "material_per_unit"}
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for rec in read_csv_rows(csv_path):
        row = {}
        for k, v in rec.items():
            key = hmap.get((k or "").strip().lower())
            if key:
                row[key] = v
        if not (row.get("ics_no") or "").strip():
            continue
        d = normalize("items", row)  # set field sesuai FIELDS["items"] + hitung cap_h
        d["created_at"] = now
        docs.append(d)
    await db.items.delete_many({})
    if docs:
        await db.items.insert_many(docs)
    await db.items.create_index([("ics_no", 1), ("type", 1)])
    await db.meta.update_one({"_id": "items_seed"},
                             {"$set": {"version": ITEMS_SEED_VERSION, "at": now, "count": len(docs)}}, upsert=True)
    logger.info("Seeded %d master items from items.csv", len(docs))


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
