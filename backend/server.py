from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from pymongo import UpdateOne
from zoneinfo import ZoneInfo
import asyncio
import hmac
import logging
import io
import re
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
        if isinstance(v, str):
            v = v.replace("\xa0", "").replace(" ", "").strip()
            if "," in v:
                v = v.replace(".", "").replace(",", ".")
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

SHIFTS = ["SHIFT 3", "SHIFT 1", "SHIFT 2"]

FIELDS = {
    "smt_production": [("date", "TANGGAL", False), ("lane", "LANE", False), ("product", "PRODUCT", False),
        ("type", "TYPE", False), ("ics_no", "ICS NO", False), ("tt", "T/T", True), ("shift", "SHIFT", False),
        ("plan_injection", "PLAN INJECTION", True), ("act_injection", "ACT INJECTION", True),
        ("plan_eva", "PLAN EVA", True), ("act_eva", "ACT EVA", True),
        ("plan_assy", "PLAN ASSY", True), ("act_assy", "ACT ASSY", True)],
    "smt_stock": [("date", "Tanggal", False), ("lane", "Lane", False), ("product", "Product", False), ("type", "Type", False), ("ics_no", "ICS No.", False)] + [
        ("shift", "SHIFT", False),
        ("group1", "GROUP 1", True), ("group2", "GROUP 2", True), ("group3", "GROUP 3", True),
        ("group4", "GROUP 4", True), ("group5", "GROUP 5", True), ("group6", "GROUP 6", True),
        ("part_ragu", "PART RAGU-RAGU", True)],
    "production_needs": BASE_FIELDS + [
        ("plan_assy", "Plan Assy Hari Ini", True), ("stock_ok_prev", "Stock OK Part Kemarin", True)],
    "variance": BASE_FIELDS + [
        ("total_stock_prev", "Total Stock Kemarin", True), ("smt_total", "Total Produksi Part", True),
        ("assy_total", "Total Produksi Assy", True), ("smt3", "Part Shift 3", True),
        ("assy3", "Assy Shift 3", True), ("actual_total_stock", "Actual Total Stock", True),
        ("reason", "Keterangan", False)],
    "items": [("lane", "Lane", False), ("product", "Product", False), ("type", "Type", False), ("ics_no", "ICS No.", False),
              ("ics_name", "ICS NAME", False), ("group", "GROUP", False),
              ("std_stock_min", "STD STOCK MIN", True), ("std_stock_max", "STD STOCK MAX", True),
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
    total_plan = num(d.get("plan_injection")) + num(d.get("plan_eva")) + num(d.get("plan_assy"))
    total_act = num(d.get("act_injection")) + num(d.get("act_eva")) + num(d.get("act_assy"))
    d["total_plan"] = r1(total_plan)
    d["total_act"] = r1(total_act)
    d["plan_part"] = r1(num(d.get("plan_injection")) + num(d.get("plan_eva")))
    # Pemetaan antar-modul (Variance/Dashboard): Total Produksi Part = ACT INJECTION + ACT EVA; Total Assy = ACT ASSY
    d["total_act_part"] = r1(num(d.get("act_injection")) + num(d.get("act_eva")))
    d["total_act_assy"] = r1(num(d.get("act_assy")))
    d["achv"] = round(total_act / total_plan * 100, 1) if total_plan else 0.0
    d["balance"] = r1(d["total_act_part"] - d["total_act_assy"])
    d["status"] = "SELESAI" if total_plan and total_act >= total_plan else ("PROSES" if total_act > 0 else "BELUM MULAI")
    return d


STOCK_INPUTS = ["group1", "group2", "group3", "group4", "group5", "group6", "part_ragu"]


def compute_smt_stock(d: dict) -> dict:
    if all(d.get(k) is None for k in STOCK_INPUTS):
        d["total"] = None
        d["status"] = "KOSONG"
        return d
    d["total"] = r1(num(d.get("group1")) + num(d.get("group2")) + num(d.get("group3"))
                    + num(d.get("group4")) + num(d.get("group5")) + num(d.get("group6")) + num(d.get("part_ragu")))
    d["status"] = "OK" if d["total"] > 0 else "KOSONG"
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
        for f in ("std_stock_min", "std_stock_max"):
            raw = body.get(f)
            d[f] = None if raw in (None, "", "-") else max(0.0, num(raw))
        bad = d.get("std_stock_min") is not None and d.get("std_stock_max") is not None and d["std_stock_min"] > d["std_stock_max"]
        d["std_warning"] = "STD MIN > MAX" if bad else ""
        g = str(body.get("group") or "").strip()
        if re.fullmatch(r"\d+(\.0+)?", g):
            g = f"GROUP {int(float(g))}"
        d["group"] = g.upper()
        d["ics_name"] = str(body.get("ics_name") or "").strip()
    if module in ("smt_stock", "smt_production") and d.get("shift") not in SHIFTS:
        d["shift"] = d.get("shift") or ""
    if module == "variance":
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
    for k in ("lane", "type", "ics_no", "product", "shift"):
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
                         product: Optional[str] = None, shift: Optional[str] = None, proses_mesin: Optional[str] = None,
                         status: Optional[str] = None, search: Optional[str] = None, group: Optional[str] = None,
                         user: dict = Depends(require_perm(module, "read"))):
        sh = shift if shift and shift != "ALL" else None
        pr = proses_mesin if proses_mesin and proses_mesin != "ALL" else None
        p = {"date_from": date_from, "date_to": date_to, "lane": lane, "type": type, "ics_no": ics_no, "search": search, "shift": sh}
        if module == "production_needs":
            out = await needs_view(p, product, pr)
        elif module == "variance":
            out = await variance_view(p, product, pr)
        else:
            docs = await coll.find(build_query(p)).sort(cfg["sort"]).to_list(20000 if module == "smt_stock" else 5000)
            out = [clean(d) for d in docs]
            if module == "smt_stock":
                out = await enrich_stock(out)
            else:
                out = await attach_proses_mesin(out)
            if product:
                out = [o for o in out if o.get("product") == product]
            if pr:
                out = [o for o in out if o.get("proses_mesin") == pr]
            if group and group != "ALL":
                out = [o for o in out if o.get("group") == group]
        if status:
            out = [o for o in out if o.get("status") == status or o.get("variance_status") == status or o.get("indikator") == status or o.get("status_part") == status]
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
            if module in ("smt_production", "smt_stock"):
                key["shift"] = d.get("shift", "")
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
    return {"found": True, "source_date": d["date"], "stock_ok_prev": num(d.get("total")),
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
    for it in await db.items.find({}, {"ics_no": 1, "type": 1, "product": 1, "tt_assy": 1, "material_per_unit": 1, "proses_mesin": 1, "ics_name": 1, "group": 1, "std_stock_min": 1, "std_stock_max": 1}).to_list(10000):
        m[(it.get("ics_no"), it.get("type"))] = it
        m.setdefault((it.get("ics_no"), None), it)
    return m


def item_of(pm: dict, ics: str, typ: str):
    return pm.get((ics, typ)) or pm.get((ics, None)) or {}


def fill_product(doc: dict, pm: dict) -> dict:
    it = item_of(pm, doc.get("ics_no"), doc.get("type"))
    if not doc.get("product"):
        doc["product"] = it.get("product") or ""
    doc["proses_mesin"] = it.get("proses_mesin") or ""
    doc["ics_name"] = it.get("ics_name") or ""
    doc["group"] = it.get("group") or ""
    doc["std_stock_min"] = it.get("std_stock_min")
    doc["std_stock_max"] = it.get("std_stock_max")
    return doc


async def attach_proses_mesin(docs: list) -> list:
    pm = await product_map()
    for d in docs:
        fill_product(d, pm)
    return docs


async def standards_map() -> dict:
    return {(s.get("lane"), s.get("product"), s.get("type")): num(s.get("standard_stock")) for s in await db.stock_standards.find({}).to_list(5000)}


def indikator(total, std):
    if std is None:
        return "BELUM DISET"
    if total is None:
        return "BELUM DICEK"
    return "PASS" if total == std else ("MINUS" if total < std else "OVER")


async def enrich_stock(docs: list) -> list:
    pm = await product_map()
    for d in docs:
        fill_product(d, pm)
        mn, mx = d.get("std_stock_min"), d.get("std_stock_max")
        d["standard_stock"] = mx
        total = num(d.get("total"))
        if mn is None and mx is None:
            d["indikator"] = "BELUM DISET"
        elif mx is not None and total > mx:
            d["indikator"] = "OVER"
        elif mn is not None and total < mn:
            d["indikator"] = "MINUS"
        else:
            d["indikator"] = "PASS"
    dates = {d.get("date") for d in docs if d.get("date")}
    sp = {(r["date"], r["ics_no"], r["type"]): r["status_part"] for r in await needs_rows_period(dates=dates)} if dates else {}
    for d in docs:
        d["status_part"] = sp.get((d.get("date"), d.get("ics_no"), d.get("type"))) or "BELUM TERSEDIA"
    return docs


async def needs_view(p: dict, product: Optional[str], proses: Optional[str] = None) -> list:
    prods = await db.smt_production.find(build_query({**p, "shift": None})).to_list(10000)
    # grup per (Tanggal + ICS No. + Type) — kondisi produksi dinilai per SHIFT dari record Produksi
    groups = {}
    for x in prods:
        k = (x.get("date"), x.get("ics_no"), x.get("type"))
        groups.setdefault(k, []).append(x)
    dates = sorted({x.get("date") for x in prods})
    stocks = await db.smt_stock.find({"date": {"$in": dates}}).to_list(20000) if dates else []
    sm = {(s.get("date"), s.get("ics_no"), s.get("type")): s for s in stocks}
    sm_ics = {}
    for s in stocks:
        sm_ics.setdefault((s.get("date"), s.get("ics_no")), s)
    pm = await product_map()
    want_shift = p.get("shift")
    out = []
    for k, recs in groups.items():
        date, ics, typ = k
        base = fill_product(clean(recs[0]), pm)
        if product and base.get("product") != product:
            continue
        it = item_of(pm, ics, typ)
        proses_mesin = it.get("proses_mesin") or ""
        if proses and proses_mesin != proses:
            continue

        def shift_on(shift_name: str, inj_only: bool) -> bool:
            for x in recs:
                if x.get("shift") == shift_name:
                    if inj_only:
                        if num(x.get("plan_injection")) > 0:
                            return True
                    elif num(x.get("plan_injection")) > 0 or num(x.get("plan_eva")) > 0 or num(x.get("plan_assy")) > 0:
                        return True
            return False

        s3 = shift_on("SHIFT 3", False)
        s1 = shift_on("SHIFT 1", True)
        s2 = shift_on("SHIFT 2", True)
        if want_shift == "SHIFT 3" and not s3:
            continue
        if want_shift == "SHIFT 1" and not s1:
            continue
        if want_shift == "SHIFT 2" and not s2:
            continue
        st = sm.get(k) or sm_ics.get((date, ics))
        stock = num(st.get("total")) if st else 0.0
        plan_assy = r1(sum(num(x.get("plan_assy")) for x in recs))
        tt_assy = num(it.get("tt_assy")) or None
        mpu = num(it.get("material_per_unit"), 1.0) or 1.0
        active = s3 or s1 or s2 or plan_assy > 0
        ws = None if (not active or not tt_assy) else (0.0 if stock <= 0 else round(stock / mpu * tt_assy / 3600, 2))
        blc = r1(stock - plan_assy)
        out.append({
            "id": base["id"], "date": date, "lane": base.get("lane"), "product": base.get("product"), "type": typ,
            "ics_no": ics, "proses_mesin": proses_mesin,
            "shift3": "ON" if s3 else "OFF", "shift1": "ON" if s1 else "OFF", "shift2": "ON" if s2 else "OFF",
            "kondisi_produksi": "ON" if (s3 or s1 or s2) else "OFF",
            "plan_assy": plan_assy, "stock_ok_today": stock, "stock_id": str(st["_id"]) if st else None, "has_stock": bool(st),
            "tt_assy": tt_assy, "material_per_unit": mpu, "waktu_shortage": ws, "blc": blc,
            "fulfillment": round(stock / plan_assy * 100, 1) if plan_assy else 100.0,
            "status": "SHORTAGE" if blc < 0 else ("PAS" if blc == 0 else "CUKUP"),
        })
    out.sort(key=lambda r: (r["date"], r.get("lane") or ""), reverse=True)
    return out


async def variance_view(p: dict, product: Optional[str], proses: Optional[str] = None) -> list:
    stocks = await db.smt_stock.find(build_query({**p, "shift": None})).sort([("date", -1), ("lane", 1)]).to_list(5000)
    all_stock = await db.smt_stock.find({}, {"date": 1, "ics_no": 1, "type": 1, "total": 1}).to_list(20000)
    hist = {}
    for s in all_stock:
        hist.setdefault((s.get("ics_no"), s.get("type")), []).append((s["date"], num(s.get("total"))))
    dates = sorted({x["date"] for x in stocks})
    prods = await db.smt_production.find({"date": {"$in": dates}}).to_list(20000) if dates else []
    # agregasi produksi per (tanggal, ics, type) menjumlahkan seluruh shift
    pmap, pmap_ics = {}, {}
    for x in prods:
        k = (x["date"], x.get("ics_no"), x.get("type"))
        a = pmap.setdefault(k, {"part": 0.0, "assy": 0.0})
        a["part"] += num(x.get("total_act_part")); a["assy"] += num(x.get("total_act_assy"))
        b = pmap_ics.setdefault((x["date"], x.get("ics_no")), {"part": 0.0, "assy": 0.0})
        b["part"] += num(x.get("total_act_part")); b["assy"] += num(x.get("total_act_assy"))
    pm = await product_map()
    out = []
    for s in stocks:
        r = fill_product(clean(s), pm)
        if product and r.get("product") != product:
            continue
        if proses and r.get("proses_mesin") != proses:
            continue
        prev = [t for d, t in hist.get((r.get("ics_no"), r.get("type")), []) if d < r["date"]]
        prev_total = None
        if prev:
            prev_total = max(((d, t) for d, t in hist[(r.get("ics_no"), r.get("type"))] if d < r["date"]), key=lambda z: z[0])[1]
        pr = pmap.get((r["date"], r.get("ics_no"), r.get("type"))) or pmap_ics.get((r["date"], r.get("ics_no")))
        smt_total = r1(pr["part"]) if pr else 0.0
        assy_total = r1(pr["assy"]) if pr else 0.0
        actual = num(r.get("total"))
        if prev_total is None:
            sistem = var = pct = None; status = "BELUM DICEK"
        else:
            sistem = r1(prev_total + smt_total - assy_total); var = r1(actual - sistem)
            pct = round(var / sistem * 100, 2) if sistem else 0.0
            status = "OK" if var == 0 else ("VARIANCE -" if var < 0 else "VARIANCE +")
        out.append({
            "id": r["id"], "date": r["date"], "lane": r.get("lane"), "product": r.get("product"), "type": r.get("type"),
            "ics_no": r.get("ics_no"), "proses_mesin": r.get("proses_mesin", ""), "total_stock_prev": prev_total,
            "smt_total": smt_total, "assy_total": assy_total,
            "has_production": bool(pr), "actual_total_stock": actual, "stock_sistem": sistem, "variance": var,
            "variance_pct": pct, "variance_status": status,
        })
    return out


# ---------------------------------------------------------------------------
# Kebutuhan Assy VS. Stock Part Production — grid format Excel (input per cell)
# ---------------------------------------------------------------------------
NEEDS_INT_FIELDS = ["plan_customer", "actual_customer", "plan_s3", "actual_s3", "plan_s1", "actual_s1", "plan_s2", "actual_s2"]
NEEDS_MESIN_FIELDS = ["status_mesin_s3", "status_mesin_s1", "status_mesin_s2"]
MESIN_OPTIONS = ["ON", "OFF", "DANDORI"]
STOCK_INT_FIELDS = ["group1", "group2", "group3", "group4", "group5", "group6", "part_ragu"]


def status_part(balance, mn, mx):
    if balance is None:
        return None
    if balance <= 0:
        return "SHORTAGE"
    if mn is None or mx is None:
        return "STD BELUM DISET"
    return "POTENSI SHORTAGE" if balance <= (mn + mx) / 2 else "TIDAK SHORTAGE"


def compute_needs_grid(r: dict) -> dict:
    k = r.get("act_stock")
    r["balance"] = None if k is None else r1(k - num(r.get("plan_customer")) + sum(num(r.get(f"actual_s{s}")) for s in (3, 1, 2)))
    mx = r.get("std_stock_max")
    r["level_stock"] = round(k / mx, 2) if k is not None and mx else None
    for s in (3, 1, 2):
        p, a = r.get(f"plan_s{s}"), r.get(f"actual_s{s}")
        r[f"balance_s{s}"] = None if p is None and a is None else r1(num(a) - num(p))
        r[f"achievement_s{s}"] = round(num(a) / num(p) * 100, 4) if num(p) > 0 else None
    r["status_part"] = status_part(r["balance"], r.get("std_stock_min"), mx)
    return r


ACT_STOCK_SHIFT = "SHIFT 2"


def shift_day(d: str, n: int) -> str:
    return (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=n)).strftime("%Y-%m-%d")


async def act_stock_by_date(q: dict) -> dict:
    """ACT STOCK JAM 01:00 tanggal D = TOTAL STOCK SHIFT 2 tanggal D-1. q = filter tanggal produksi."""
    dq = q.get("date")
    if isinstance(dq, dict) and "$in" in dq:
        sq = {"date": {"$in": [shift_day(d, -1) for d in dq["$in"]]}}
    elif isinstance(dq, dict):
        sq = {"date": {k: shift_day(v, -1) for k, v in dq.items()}}
    elif isinstance(dq, str):
        sq = {"date": shift_day(dq, -1)}
    else:
        sq = {}
    out = {}
    for st in await db.smt_stock.find({**sq, "shift": ACT_STOCK_SHIFT}).sort("updated_at", 1).to_list(200000):
        if st.get("total") is None or not st.get("date"):
            continue
        out.setdefault(shift_day(st["date"], 1), {})[(st.get("ics_no"), st.get("type"))] = num(st.get("total"))
    return out


async def shift3_stock_map(date: str) -> dict:
    return (await act_stock_by_date({"date": date})).get(date, {})


def needs_row(date: str, it: Optional[dict], ent: Optional[dict], stk: dict, ics: str, typ: str) -> dict:
    it = it or {}
    ent = ent or {}
    r = {"id": f"{date}|{ics}|{typ}", "date": date, "ics_no": ics, "type": typ, "master_found": bool(it)}
    for f in ("lane", "product", "ics_name", "proses_mesin", "group"):
        r[f] = it.get(f) or ""
    r["std_stock_min"] = it.get("std_stock_min")
    r["std_stock_max"] = it.get("std_stock_max")
    r["act_stock"] = stk.get((ics, typ))
    for f in NEEDS_INT_FIELDS + NEEDS_MESIN_FIELDS:
        r[f] = ent.get(f)
    r["updated_by_name"] = ent.get("updated_by_name")
    r["updated_at"] = ent.get("updated_at")
    return compute_needs_grid(r)


async def needs_rows_period(date_from: Optional[str] = None, date_to: Optional[str] = None, dates=None) -> list:
    q = {"date": {"$in": list(dates)}} if dates is not None else build_query({"date_from": date_from, "date_to": date_to})
    ents = {(e.get("date"), e.get("ics_no"), e.get("type")): e for e in await db.needs_entries.find(q).to_list(200000)}
    stk = await act_stock_by_date(q)
    keys = set(ents) | {(d, i, t) for d, m in stk.items() for (i, t) in m}
    items = {(it.get("ics_no"), it.get("type")): it for it in await db.items.find({}).to_list(20000)}
    return [needs_row(d, items.get((i, t)), ents.get((d, i, t)), stk.get(d, {}), i, t) for (d, i, t) in sorted(keys)]


def valid_date(date: str) -> str:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except Exception:
        raise HTTPException(400, "Format tanggal harus YYYY-MM-DD")
    return date


MAX_GRID_DAYS = 31


def date_list(date_from: str, date_to: str) -> list:
    d0, d1 = datetime.strptime(valid_date(date_from), "%Y-%m-%d"), datetime.strptime(valid_date(date_to), "%Y-%m-%d")
    if d1 < d0:
        raise HTTPException(400, "SAMPAI TANGGAL tidak boleh lebih awal dari DARI TANGGAL")
    n = (d1 - d0).days + 1
    if n > MAX_GRID_DAYS:
        raise HTTPException(400, f"Periode maksimal {MAX_GRID_DAYS} hari")
    return [(d0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


@api.get("/needs-grid")
async def needs_grid(date: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
                     group: Optional[str] = None, user: dict = Depends(require_perm("production_needs", "read"))):
    if date and not date_from:
        date_from = date_to = date
    if not date_from:
        date_from = date_to = today_wib()
    dates = date_list(date_from, date_to or date_from)
    grp = group if group and group != "ALL" else None
    iq = {"group": grp} if grp else {}
    items = await db.items.find(iq).sort([("lane", 1), ("type", 1)]).to_list(20000)
    ents = {}
    for e in await db.needs_entries.find({"date": {"$in": dates}}).to_list(200000):
        ents[(e.get("date"), e.get("ics_no"), e.get("type"))] = e
    stk = await act_stock_by_date({"date": {"$in": dates}})
    master_keys = []
    seen = set()
    for it in items:
        key = (it.get("ics_no") or "", it.get("type") or "")
        if key not in seen:
            seen.add(key)
            master_keys.append((key, it))
    all_master = seen if not grp else {(it.get("ics_no"), it.get("type")) for it in await db.items.find({}, {"ics_no": 1, "type": 1}).to_list(20000)}
    out = []
    for d in dates:
        for key, it in master_keys:
            out.append(needs_row(d, it, ents.get((d, *key)), stk.get(d, {}), *key))
        if not grp:
            for (ed, ei, et), e in ents.items():
                if ed == d and (ei, et) not in all_master:
                    out.append(needs_row(d, None, e, stk.get(d, {}), ei, et))
    return out


class ClearBody(BaseModel):
    rows: list


@api.post("/needs-grid/clear")
async def needs_grid_clear(body: ClearBody, request: Request, user: dict = Depends(require_perm("production_needs", "write"))):
    if not body.rows:
        raise HTTPException(400, "Tidak ada data yang dipilih")
    if len(body.rows) > 50000:
        raise HTTPException(400, "Terlalu banyak data dipilih")
    cleared = 0
    for r in body.rows:
        if not isinstance(r, dict):
            continue
        key = {"date": str(r.get("date") or ""), "ics_no": str(r.get("ics_no") or ""), "type": str(r.get("type") or "")}
        doc = await db.needs_entries.find_one_and_delete(key)
        if doc:
            cleared += 1
            await log_audit(request, user, "DELETE", "production_needs", str(doc["_id"]), clean(dict(doc)), None,
                            f"Hapus (kosongkan) input Kebutuhan · {key['ics_no']} {key['type']} · {key['date']}")
    return {"selected": len(body.rows), "cleared": cleared}


class CellBody(BaseModel):
    field: str
    value: Optional[Any] = None
    date: Optional[str] = None
    ics_no: Optional[str] = None
    type: Optional[str] = None


def parse_int_cell(v):
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    if isinstance(v, bool):
        raise HTTPException(400, "Nilai harus berupa angka bulat")
    if isinstance(v, (int, float)):
        if float(v) != int(v):
            raise HTTPException(400, "Nilai harus berupa angka bulat (tanpa desimal)")
        v = int(v)
    else:
        s = str(v).strip()
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")
        if not s.isdigit():
            raise HTTPException(400, "Nilai harus berupa angka bulat positif")
        v = int(s)
    if v < 0:
        raise HTTPException(400, "Nilai tidak boleh negatif")
    return v


@api.patch("/needs-grid/cell")
async def needs_grid_cell(body: CellBody, request: Request, user: dict = Depends(require_perm("production_needs", "write"))):
    date = valid_date(body.date or "")
    ics, typ = (body.ics_no or "").strip(), (body.type or "").strip()
    if body.field in NEEDS_INT_FIELDS:
        value = parse_int_cell(body.value)
    elif body.field in NEEDS_MESIN_FIELDS:
        value = None if body.value in (None, "") else str(body.value).upper()
        if value is not None and value not in MESIN_OPTIONS:
            raise HTTPException(400, "STATUS MESIN hanya boleh ON, OFF, atau DANDORI")
    else:
        raise HTTPException(400, f"Kolom {body.field} tidak dapat diedit")
    key = {"date": date, "ics_no": ics, "type": typ}
    it = await db.items.find_one({"ics_no": ics, "type": typ})
    existing = await db.needs_entries.find_one(key)
    if not it and not existing:
        raise HTTPException(404, "Data Master Item belum tersedia untuk ICS NO / TYPE ini")
    now = datetime.now(timezone.utc).isoformat()
    sets = {body.field: value, "updated_at": now, "updated_by": user["id"], "updated_by_name": user["name"],
            f"{body.field}_updated_at": now, f"{body.field}_updated_by": user["name"]}
    res = await db.needs_entries.find_one_and_update(
        key, {"$set": sets, "$setOnInsert": {**key, "created_at": now, "created_by": user["id"], "created_by_name": user["name"]}},
        upsert=True, return_document=True)
    await log_audit(request, user, "UPDATE", "production_needs", str(res["_id"]),
                    {**key, body.field: (existing or {}).get(body.field)}, {**key, body.field: value},
                    f"Input cell {body.field} · {ics} {typ} · {date}")
    stk = await shift3_stock_map(date)
    return needs_row(date, it, res, stk, ics, typ)


class BulkIds(BaseModel):
    ids: list


@api.post("/smt-stock/bulk-delete")
async def smt_stock_bulk_delete(body: BulkIds, request: Request, user: dict = Depends(require_perm("smt_stock", "write"))):
    ids = [i for i in body.ids if isinstance(i, str)]
    if not ids:
        raise HTTPException(400, "Tidak ada data yang dipilih")
    oids = []
    for i in ids:
        try:
            oids.append(ObjectId(i))
        except Exception:
            continue
    docs = await db.smt_stock.find({"_id": {"$in": oids}}).to_list(len(oids) + 1)
    res = await db.smt_stock.delete_many({"_id": {"$in": [d["_id"] for d in docs]}})
    for d in docs:
        await log_audit(request, user, "DELETE", "smt_stock", str(d["_id"]), clean(dict(d)), None, "Hapus data (checklist)")
    if res.deleted_count:
        await notify_users(user, "smt_stock", f"{user['name']} menghapus {res.deleted_count} data Stock Part Production (checklist).")
    return {"selected": len(ids), "deleted": res.deleted_count}


def today_wib() -> str:
    return datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d")


async def generate_stock_day(date: str, source: str, by: str, run_id: Optional[str] = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    log_id = (await db.generate_logs.insert_one({"date": date, "source": source, "by": by, "run_id": run_id, "status": "RUNNING",
                                                  "started_at": now})).inserted_id
    try:
        items = await db.items.find({}).to_list(20000)
        ops, seen = [], set()
        for it in items:
            key = (it.get("ics_no") or "", it.get("type") or "")
            if not key[0] or key in seen:
                continue
            seen.add(key)
            for sh in ("SHIFT 3", "SHIFT 1", "SHIFT 2"):
                doc = {"date": date, "ics_no": key[0], "type": key[1], "shift": sh, "lane": it.get("lane") or "",
                       "product": it.get("product") or "", **{k: None for k in STOCK_INPUTS}, "total": None, "status": "KOSONG",
                       "generated": True, "created_at": now, "created_by": "system", "created_by_name": f"SYSTEM ({source})",
                       "updated_at": now, "updated_by": "system", "updated_by_name": f"SYSTEM ({source})"}
                ops.append(UpdateOne({"date": date, "ics_no": key[0], "type": key[1], "shift": sh}, {"$setOnInsert": doc}, upsert=True))
        inserted = 0
        for i in range(0, len(ops), 1000):
            res = await db.smt_stock.bulk_write(ops[i:i + 1000], ordered=False)
            inserted += res.upserted_count
        result = {"status": "SUCCESS", "inserted": inserted, "existing": len(ops) - inserted, "expected": len(ops),
                  "finished_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.exception("Generate stock gagal")
        result = {"status": "FAILED", "error": str(e), "finished_at": datetime.now(timezone.utc).isoformat()}
    await db.generate_logs.update_one({"_id": log_id}, {"$set": result})
    return {"date": date, **result}


class GenerateBody(BaseModel):
    date: Optional[str] = None


@api.post("/smt-stock/generate")
async def smt_stock_generate(body: GenerateBody, request: Request, user: dict = Depends(require_perm("smt_stock", "write"))):
    if user.get("role") != "admin":
        raise HTTPException(403, "Hanya admin yang dapat menjalankan generate manual")
    date = valid_date(body.date or today_wib())
    res = await generate_stock_day(date, "MANUAL", user["name"])
    await log_audit(request, user, "CREATE", "smt_stock", date, None, res, f"Generate data harian {date} dari Master Item")
    if res["status"] != "SUCCESS":
        raise HTTPException(500, f"Generate gagal: {res.get('error')}")
    return res


@api.get("/smt-stock/generate-logs")
async def smt_stock_generate_logs(user: dict = Depends(require_perm("smt_stock", "read"))):
    return [clean(d) for d in await db.generate_logs.find({}).sort("started_at", -1).to_list(15)]


async def run_cron_generate(run_id: str):
    await generate_stock_day(today_wib(), "AUTO 00:01 WIB", "SYSTEM", run_id)


@api.post("/cron/daily-generate")
async def cron_daily_generate(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    secret = os.environ.get("WEBHOOK_CRON_SECRET") or ""
    auth = request.headers.get("authorization") or ""
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not secret or not token or not hmac.compare_digest(token, secret):
        raise HTTPException(401, "Unauthorized")
    try:
        body = await request.json()
    except Exception:
        body = None
    if body is not None and not isinstance(body, dict):
        raise HTTPException(400, "Invalid body")
    run_id = request.headers.get("x-webhook-id") or (body or {}).get("run_id") or f"manual-{datetime.now(timezone.utc).isoformat()}"
    try:
        await db.cron_runs.insert_one({"_id": run_id, "at": datetime.now(timezone.utc).isoformat(), "job": "daily-generate"})
    except DuplicateKeyError:
        return {"status": "duplicate", "run_id": run_id}
    asyncio.create_task(run_cron_generate(run_id))
    return {"status": "accepted", "run_id": run_id}


@api.patch("/smt-stock/{rid}/cell")
async def smt_stock_cell(rid: str, body: CellBody, request: Request, user: dict = Depends(require_perm("smt_stock", "write"))):
    if body.field not in STOCK_INT_FIELDS:
        raise HTTPException(400, f"Kolom {body.field} tidak dapat diedit")
    value = parse_int_cell(body.value)
    existing = await db.smt_stock.find_one({"_id": oid(rid)})
    if not existing:
        raise HTTPException(404, "Data tidak ditemukan")
    d = compute_smt_stock({**existing, body.field: value})
    sets = {body.field: value, "total": d["total"], "status": d["status"]}
    stamp(sets, user, False)
    await db.smt_stock.update_one({"_id": existing["_id"]}, {"$set": sets})
    doc = clean(await db.smt_stock.find_one({"_id": existing["_id"]}))
    ref = {k: existing.get(k, "") for k in ("date", "ics_no", "type", "shift")}
    await log_audit(request, user, "UPDATE", "smt_stock", rid, {**ref, body.field: existing.get(body.field), "total": existing.get("total")},
                    {**ref, body.field: value, "total": doc.get("total")}, f"Input cell {body.field}")
    return (await enrich_stock([doc]))[0]


# ---------------------------------------------------------------------------
# IMPORT EXCEL — Kebutuhan Assy VS. Stock Part Production
# ---------------------------------------------------------------------------
NEEDS_EXPORT_COLS = [
    ("date", "TANGGAL"), ("lane", "LANE"), ("product", "PRODUCT"), ("type", "TYPE"), ("ics_no", "ICS NO"), ("ics_name", "ICS NAME"),
    ("proses_mesin", "PROSES MESIN"), ("group", "GROUP"), ("std_stock_min", "STD STOCK MIN"), ("std_stock_max", "STD STOCK MAX"),
    ("act_stock", "ACT STOCK JAM 01:00"), ("plan_customer", "PLAN CUSTOMER (ASSY)"), ("actual_customer", "ACTUAL CUSTOMER (ASSY)"),
    ("balance", "BALANCE"), ("level_stock", "LEVEL STOCK (DAY)"), ("status_part", "STATUS PART"),
] + [c for s_ in (3, 1, 2) for c in [(f"plan_s{s_}", f"PLAN S{s_}"), (f"actual_s{s_}", f"ACTUAL S{s_}"), (f"achievement_s{s_}", f"ACHIEVEMENT S{s_}"),
                                       (f"balance_s{s_}", f"BALANCE S{s_}"), (f"status_mesin_s{s_}", f"STATUS MESIN S{s_}")]]
NEEDS_IMPORT_FIELDS = NEEDS_INT_FIELDS + NEEDS_MESIN_FIELDS


def needs_header_map() -> Dict[str, str]:
    m = {}
    for k, label in NEEDS_EXPORT_COLS:
        m[label.lower()] = k
        m[k] = k
    m.update({"tanggal produksi": "date", "date": "date", "ics no.": "ics_no", "part number": "ics_no",
              "plan customer": "plan_customer", "actual customer": "actual_customer",
              "plan customer assy": "plan_customer", "actual customer assy": "actual_customer"})
    for s_ in (3, 1, 2):
        m[f"act s{s_}"] = f"actual_s{s_}"
    return m


def parse_date_cell(v) -> Optional[str]:
    s_ = str(v or "").strip()
    if not s_:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}( 00:00:00)?", s_):
        return s_[:10]
    if re.fullmatch(r"\d+(\.0)?", s_):
        n = int(float(s_))
        if 20000 < n < 80000:
            return (datetime(1899, 12, 30) + timedelta(days=n)).strftime("%Y-%m-%d")
        return None
    try:
        return pd.to_datetime(s_, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def parse_ics(v) -> str:
    s_ = str(v or "").strip()
    return s_.split(".")[0].zfill(10) if s_.replace(".", "").isdigit() else s_


async def analyze_needs_import(file: UploadFile, mode: str):
    if mode not in ("add", "update"):
        raise HTTPException(400, "Mode import harus 'add' (Tambah Data) atau 'update' (Update Data)")
    try:
        dff = parse_dataframe(await file.read(), file.filename)
    except Exception as e:
        raise HTTPException(400, f"Gagal membaca file: {e}")
    hm = needs_header_map()
    cols = {c: hm.get(str(c).strip().lower()) for c in dff.columns}
    found = set(cols.values())
    missing = [lab for k, lab in (("date", "TANGGAL"), ("ics_no", "ICS NO"), ("type", "TYPE")) if k not in found]
    if missing:
        raise HTTPException(400, f"Header wajib tidak ditemukan: {', '.join(missing)}. Gunakan template Kebutuhan Assy.")
    input_cols = [k for k in NEEDS_IMPORT_FIELDS if k in found]
    if not input_cols:
        raise HTTPException(400, "Tidak ada kolom input (PLAN CUSTOMER, ACTUAL CUSTOMER, PLAN/ACTUAL S3/S1/S2, STATUS MESIN) pada file")
    unknown = [c for c, k in cols.items() if k is None]
    reference = [c for c, k in cols.items() if k and k not in NEEDS_IMPORT_FIELDS and k not in ("date", "ics_no", "type")]
    items = {(it.get("ics_no"), it.get("type")) for it in await db.items.find({}, {"ics_no": 1, "type": 1}).to_list(20000)}
    seen, rows = {}, []
    for idx, rec in enumerate(dff.to_dict(orient="records")):
        raw = {k: rec[c] for c, k in cols.items() if k}
        r = {"row": idx + 2, "date": parse_date_cell(raw.get("date")), "ics_no": parse_ics(raw.get("ics_no")),
             "type": " ".join(str(raw.get("type") or "").split()), "values": {}, "errors": []}
        if not r["date"]:
            r["errors"].append(f"TANGGAL tidak valid ({raw.get('date') or 'kosong'})")
        if not r["ics_no"] or not r["type"]:
            r["errors"].append("ICS NO / TYPE wajib diisi")
        elif (r["ics_no"], r["type"]) not in items:
            r["errors"].append("ICS NO + TYPE belum terdaftar di Master Item")
        for k in input_cols:
            v = raw.get(k)
            if v is None or str(v).strip() in ("", "-"):
                continue
            label = dict(NEEDS_EXPORT_COLS)[k]
            if k in NEEDS_INT_FIELDS:
                sv = str(v).strip()
                if re.fullmatch(r"\d+\.0+", sv):
                    sv = sv.split(".")[0]
                try:
                    r["values"][k] = parse_int_cell(sv)
                except HTTPException:
                    r["errors"].append(f"{label} harus angka bulat ≥ 0 ({v})")
            else:
                sv = str(v).strip().upper()
                if sv not in MESIN_OPTIONS:
                    r["errors"].append(f"{label} harus ON/OFF/DANDORI ({v})")
                else:
                    r["values"][k] = sv
        key = (r["date"], r["ics_no"], r["type"])
        if not r["errors"]:
            if key in seen:
                r["errors"].append(f"Duplikat dalam file (sama dengan baris {seen[key]})")
            else:
                seen[key] = r["row"]
        rows.append(r)
    valid_keys = [(r["date"], r["ics_no"], r["type"]) for r in rows if not r["errors"]]
    existing = set()
    for d_ in {k[0] for k in valid_keys}:
        for e in await db.needs_entries.find({"date": d_}, {"ics_no": 1, "type": 1}).to_list(20000):
            existing.add((d_, e.get("ics_no"), e.get("type")))
    for r in rows:
        if r["errors"]:
            r["action"] = "gagal"
        elif not r["values"]:
            r["action"] = "dilewati"; r["note"] = "Tidak ada nilai input"
        elif (r["date"], r["ics_no"], r["type"]) in existing:
            r["action"] = "diperbarui" if mode == "update" else "dilewati"
            if mode == "add":
                r["note"] = "Data sudah ada (mode Tambah Data)"
        else:
            r["action"] = "baru"
    return rows, input_cols, unknown, reference


def import_counts(rows):
    c = {"total": len(rows), "baru": 0, "diperbarui": 0, "dilewati": 0, "gagal": 0}
    for r in rows:
        c[r["action"]] += 1
    return c


@api.get("/needs-grid/import/template")
async def needs_import_template(date: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
                                group: Optional[str] = None, user: dict = Depends(require_perm("production_needs", "read"))):
    rows = await needs_grid(date, date_from, date_to, group, user) if (date or date_from) else []
    date = date or (f"{date_from}_{date_to}" if date_from else None)
    wb = Workbook(); ws = wb.active; ws.title = "Kebutuhan Assy"
    ws.append([lab for _, lab in NEEDS_EXPORT_COLS])
    for r in rows:
        ws.append([r.get(k) for k, _ in NEEDS_EXPORT_COLS])
    for i, (_, lab) in enumerate(NEEDS_EXPORT_COLS, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = max(10, len(lab) + 2)
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="kebutuhan_assy_{date or "template"}.xlsx"'})


@api.post("/needs-grid/import/preview")
async def needs_import_preview(file: UploadFile = File(...), mode: str = Form("update"),
                               user: dict = Depends(require_perm("production_needs", "write"))):
    rows, input_cols, unknown, reference = await analyze_needs_import(file, mode)
    return {"counts": import_counts(rows), "input_columns": input_cols, "unknown_columns": unknown,
            "reference_columns": reference, "rows": rows[:200], "mode": mode}


@api.post("/needs-grid/import/confirm")
async def needs_import_confirm(request: Request, file: UploadFile = File(...), mode: str = Form("update"),
                               user: dict = Depends(require_perm("production_needs", "write"))):
    fname = file.filename
    rows, _, _, _ = await analyze_needs_import(file, mode)
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        if r["action"] not in ("baru", "diperbarui"):
            continue
        key = {"date": r["date"], "ics_no": r["ics_no"], "type": r["type"]}
        sets = {**r["values"], "updated_at": now, "updated_by": user["id"], "updated_by_name": user["name"]}
        for f in r["values"]:
            sets[f"{f}_updated_at"] = now; sets[f"{f}_updated_by"] = user["name"]
        res = await db.needs_entries.find_one_and_update(
            key, {"$set": sets, "$setOnInsert": {**key, "created_at": now, "created_by": user["id"], "created_by_name": user["name"]}},
            upsert=True, return_document=True)
        await log_audit(request, user, "CREATE" if r["action"] == "baru" else "UPDATE", "production_needs", str(res["_id"]),
                        None, {**key, **r["values"]}, f"Import {fname}")
    counts = import_counts(rows)
    if counts["baru"] or counts["diperbarui"]:
        await notify_users(user, "production_needs", f"Import Kebutuhan Assy: {counts['baru']} baru, {counts['diperbarui']} diperbarui oleh {user['name']} pada {fmt_ts(now)}.")
    return {"counts": counts, "failed": [r for r in rows if r["action"] == "gagal"][:200]}


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
            "proses_mesin": sorted({x for x in await db.items.distinct("proses_mesin") if x}),
            "groups": [f"GROUP {i}" for i in range(1, 7)],
            "master_groups": sorted({x for x in await db.items.distinct("group") if x}, key=lambda g: (len(g), g)),
            "shifts": SHIFTS,
            "stock_status": ["OK", "KOSONG"],
            "indikator": ["PASS", "MINUS", "OVER", "BELUM DISET"],
            "lamp_status": ["SELESAI", "PROSES", "BELUM MULAI"],
            "needs_status": ["CUKUP", "PAS", "SHORTAGE", "BELUM DICEK"],
            "status_part": ["SHORTAGE", "POTENSI SHORTAGE", "TIDAK SHORTAGE", "STD BELUM DISET", "BELUM TERSEDIA"],
            "status_mesin": MESIN_OPTIONS,
            "variance_status": ["OK", "VARIANCE +", "VARIANCE -", "BELUM DICEK"]}


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
STATUS_RANK = {"SHORTAGE": 3, "POTENSI SHORTAGE": 2, "TIDAK SHORTAGE": 1, "STD BELUM DISET": 0}


def pct_or_none(a, p):
    return round(a / p * 100, 2) if p else None


def achievement_bucket(ach: float) -> str:
    if ach > 97:
        return "gt97"
    if ach > 96:
        return "b96_97"
    if ach >= 90:
        return "mid"
    return "lt90"


@api.get("/dashboard/summary")
async def dashboard_summary(date_from: Optional[str] = None, date_to: Optional[str] = None, product: Optional[str] = None,
                            user: dict = Depends(get_current_user)):
    all_rows = await needs_rows_period(date_from, date_to)
    rows = [r for r in all_rows if r.get("master_found")]
    items = await db.items.find({}, {"type": 1, "group": 1, "ics_no": 1, "product": 1, "ics_name": 1}).to_list(20000)
    if product:
        items = [it for it in items if it.get("product") == product]
        rows = [r for r in rows if r.get("product") == product]
    sq = build_query({"date_from": date_from, "date_to": date_to})
    stocks = await db.smt_stock.find(sq).to_list(200000)

    # PRODUKSI PART PRODUCTION (Σ PLAN/ACTUAL S3+S1+S2) & LAMP ASSY (PLAN/ACTUAL CUSTOMER)
    sh = (3, 1, 2)
    part_plan = sum(num(r.get(f"plan_s{x}")) for r in rows for x in sh)
    part_act = sum(num(r.get(f"actual_s{x}")) for r in rows for x in sh)
    assy_plan = sum(num(r.get("plan_customer")) for r in rows)
    assy_act = sum(num(r.get("actual_customer")) for r in rows)

    # Chart: per tanggal, semua TYPE diakumulasi
    by_date = {}
    for r in rows:
        t = by_date.setdefault(r["date"], {"date": r["date"], "plan": 0.0, "actual": 0.0, "has": False})
        if r.get("plan_customer") is not None or any(r.get(f"actual_s{x}") is not None for x in sh):
            t["has"] = True
        t["plan"] += num(r.get("plan_customer"))
        t["actual"] += sum(num(r.get(f"actual_s{x}")) for x in sh)
    trend = [{"date": t["date"], "plan": t["plan"], "actual": t["actual"], "pct": pct_or_none(t["actual"], t["plan"])}
             for t in sorted(by_date.values(), key=lambda x: x["date"]) if t["has"]]
    if not (date_from or date_to):
        trend = trend[-31:]

    # Pencapaian per TYPE unik: total ACTUAL / total PLAN (S3+S1+S2) pada periode
    type_agg = {}
    for r in rows:
        a = type_agg.setdefault(r.get("type") or "-", [0.0, 0.0])
        a[0] += sum(num(r.get(f"plan_s{x}")) for x in sh)
        a[1] += sum(num(r.get(f"actual_s{x}")) for x in sh)
    planned = {t: v for t, v in type_agg.items() if v[0] > 0}
    buckets = {"gt97": [], "b96_97": [], "mid": [], "lt90": []}
    for t, (p_, a_) in planned.items():
        ach = a_ / p_ * 100
        buckets[achievement_bucket(ach)].append(ach)
    achievement = {k: {"total_plan": len(planned), "act": len(v), "average": round(sum(v) / len(v), 2) if v else None}
                   for k, v in buckets.items()}

    # Item Shortage: TOTAL PART = TYPE unik Master Item; status per TYPE = tanggal terakhir (status terburuk bila >1 ICS)
    master_types = {it.get("type") for it in items if it.get("type")}
    latest = {}
    for r in rows:
        if not r.get("status_part"):
            continue
        t = r.get("type")
        cur = latest.get(t)
        if not cur or r["date"] > cur[0] or (r["date"] == cur[0] and STATUS_RANK[r["status_part"]] > STATUS_RANK[cur[1]]):
            latest[t] = (r["date"], r["status_part"])
    st_vals = [v[1] for t, v in latest.items() if t in master_types]
    shortage = {
        "total_part": len(master_types),
        "tidak_shortage": st_vals.count("TIDAK SHORTAGE"),
        "potensi_shortage": st_vals.count("POTENSI SHORTAGE"),
        "shortage": st_vals.count("SHORTAGE"),
        "std_belum_diset": st_vals.count("STD BELUM DISET"),
        "with_status": len(st_vals),
        "no_status": len(master_types) - len(st_vals),
        "latest_date": max((v[0] for v in latest.values()), default=None),
    }

    # Top Shortage (BLC): balance terendah, data terakhir per item
    last_row = {}
    for r in rows:
        if r.get("balance") is None:
            continue
        k = (r["ics_no"], r["type"])
        if k not in last_row or r["date"] > last_row[k]["date"]:
            last_row[k] = r
    top_shortage = [{"id": f"{r['date']}|{r['id']}", "date": r["date"], "type": r["type"], "ics_no": r["ics_no"], "product": r.get("product"),
                     "lane": r.get("lane"), "ics_name": r.get("ics_name"), "balance": r["balance"], "status_part": r.get("status_part"),
                     "act_stock": r.get("act_stock"), "plan_customer": r.get("plan_customer")}
                    for r in sorted((x for x in last_row.values() if x["balance"] <= 0), key=lambda x: x["balance"])[:10]]

    # Komposisi Stock Part per GROUP (Master Item) dari Stock Part Production: record terbaru per item
    shift_ord = {"SHIFT 3": 0, "SHIFT 1": 1, "SHIFT 2": 2}
    item_group = {(it.get("ics_no"), it.get("type")): (it.get("group") or "").strip() for it in items}
    latest_stock = {}
    for st in stocks:
        k = (st.get("ics_no"), st.get("type"))
        if k not in item_group or st.get("total") is None:
            continue
        o = (st.get("date") or "", shift_ord.get(st.get("shift"), -1))
        if k not in latest_stock or o > latest_stock[k][0]:
            latest_stock[k] = (o, num(st.get("total")))
    short_types = {t for t, v in latest.items() if v[1] == "SHORTAGE"}
    groups_found = sorted({f"GROUP {i}" for i in range(1, 7)} | {g for g in item_group.values() if g}, key=lambda g: (len(g), g))
    group_composition = []
    for g in groups_found:
        keys = [k for k, v in latest_stock.items() if item_group.get(k) == g]
        types = {k[1] for k in keys}
        group_composition.append({"group": g, "total_type": len(types), "total_stock": sum(latest_stock[k][1] for k in keys),
                                  "shortage_type": len(types & short_types)})

    return {
        "resume": {
            "part_production": {"total_plan": part_plan, "act_prod": part_act, "pct": pct_or_none(part_act, part_plan)},
            "lamp_assy": {"total_plan": assy_plan, "act_prod": assy_act, "pct": pct_or_none(assy_act, assy_plan)},
            "shortage": shortage,
            "achievement": achievement,
        },
        "group_composition": group_composition,
        "smt_trend": trend,
        "top_shortage": top_shortage,
        "period": {"date_from": date_from, "date_to": date_to, "rows": len(rows), "excluded_no_master": len(all_rows) - len(rows),
                   "generated_at": datetime.now(timezone.utc).isoformat()},
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
    for skip in ("cap/h", "total plan", "total act", "achv %", "balance", "total act part", "total act assy", "plan part"):
        m[skip] = "__skip__"
    return m


def decode_text(b: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


COMPUTED_KEYS = {"std_warning", "cap_h", "total", "status", "total_act_part", "total_act_assy", "plan_part", "achievement", "balance"}


def parse_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = (filename or "").lower()
    if name.endswith(".csv") or name.endswith(".txt"):
        dff = pd.read_csv(io.StringIO(decode_text(file_bytes)), dtype=str, sep=None, engine="python")
    elif name.endswith((".xlsx", ".xlsm", ".xls")):
        dff = pd.read_excel(io.BytesIO(file_bytes), dtype=str, engine="xlrd" if name.endswith(".xls") else None)
    else:
        raise ValueError("Format file harus .xlsx, .xls, atau .csv")
    dff.columns = [" ".join(str(c).replace("\xa0", " ").split()) for c in dff.columns]
    dff = dff.loc[:, [not str(c).lower().startswith("unnamed") for c in dff.columns]]
    dff = dff.map(lambda v: v.replace("\xa0", " ").strip() if isinstance(v, str) else v)
    dff = dff.replace("", None).dropna(how="all")
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
        try:
            rows.append(normalize(module, r))
        except HTTPException as e:
            rows.append({**r, "_error": e.detail})
    return rows, unknown


def import_row_valid(dataset: str, r: dict) -> bool:
    """Baris dianggap valid jika field kunci dataset lengkap.
    - dataset dengan 'key' (mis. stock-standards: lane+product+type) → cek key tsb, TIDAK butuh ics_no.
    - dataset lain → butuh ics_no, dan butuh date kecuali no_date.
    """
    if r.get("_error"):
        return False
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
        if not import_row_valid(dataset, r):
            continue
        ck = DATASETS[dataset].get("key")
        key = {k: r.get(k, "") for k in ck} if ck else ({"ics_no": r["ics_no"], "type": r["type"]} if no_date else {"date": r.get("date"), "ics_no": r["ics_no"], "type": r["type"]})
        if not ck and module in ("smt_production", "smt_stock"):
            key["shift"] = r.get("shift", "")
        if await db[module].find_one(key):
            duplicates += 1; r["_duplicate"] = True
    columns = [k for k, _, _ in FIELDS[module]] + [k for k in rows[0].keys() if rows and k not in [f[0] for f in FIELDS[module]]] if rows else []
    warnings = sum(1 for r in rows if r.get("std_warning"))
    return {"columns": columns, "rows": rows[:100], "total": len(rows), "invalid": invalid, "unknown_columns": unknown,
            "duplicates": duplicates, "new": max(0, len(rows) - invalid - duplicates), "warnings": warnings}


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
    hm = header_map(module)
    present = {hm.get(str(c).strip().lower()) for c in dff.columns} - {None, "__skip__"}
    now = datetime.now(timezone.utc).isoformat()
    inserted = updated = skipped = 0
    no_date = DATASETS[dataset].get("no_date")
    for r in rows:
        ck = DATASETS[dataset].get("key")
        if r.get("_error"):
            skipped += 1
            continue
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
            if module in ("smt_production", "smt_stock"):
                key["shift"] = r.get("shift", "")
        existing = await db[module].find_one(key)
        if existing:
            try:
                merged = normalize(module, {**existing, **{k: v for k, v in r.items() if k in present}})
            except HTTPException:
                skipped += 1
                continue
            r = {k: v for k, v in merged.items() if k in present or k not in existing or k in COMPUTED_KEYS}
            stamp(r, user, False)
            await db[module].update_one({"_id": existing["_id"]}, {"$set": r}); updated += 1
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


class ExportBody(BaseModel):
    filename: str
    columns: list
    rows: list


@api.post("/export/xlsx")
async def export_xlsx(body: ExportBody, user: dict = Depends(get_current_user)):
    wb = Workbook(); ws = wb.active; ws.title = "data"
    cols = [c for c in body.columns if isinstance(c, dict) and c.get("key")]
    ws.append([c.get("label") or c["key"] for c in cols])
    for r in body.rows:
        line = []
        for c in cols:
            v = r.get(c["key"]) if isinstance(r, dict) else None
            line.append("" if v is None else v)
        ws.append(line)
    for i, c in enumerate(cols, 1):
        letter = ws.cell(1, i).column_letter
        ws.column_dimensions[letter].width = max(10, len(str(c.get("label") or c["key"])) + 2)
        if c.get("text"):
            for cell in ws[letter][1:]:
                cell.value = "" if cell.value in (None, "") else str(cell.value)
                cell.number_format = "@"
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", body.filename or "export") + ".xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


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
BACKUP_COLLECTIONS = DATA_MODULES + ["needs_entries", "users", "audit_log", "notifications"]
RESTORE_COLLECTIONS = DATA_MODULES + ["needs_entries"]


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



ITEMS_SEED_VERSION = 3


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
    await db.needs_entries.create_index([("date", 1), ("ics_no", 1), ("type", 1)], unique=True)
    await db.smt_stock.create_index([("date", 1), ("shift", 1)])
    await db.generate_logs.create_index([("started_at", -1)])
    try:
        await db.smt_stock.create_index([("date", 1), ("ics_no", 1), ("type", 1), ("shift", 1)], unique=True, name="uniq_stock_key")
    except Exception as e:
        logger.warning(f"Index unik smt_stock tidak dibuat (ada data ganda lama): {e}")
    await db.notifications.create_index([("user_id", 1), ("read", 1), ("ts", -1)])
    await seed_admin()
    await seed_demo_users()
    await seed_from_excel()
    await seed_items()


@app.on_event("shutdown")
async def shutdown():
    client.close()
