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
    "smt_production": "Produksi SMT",
    "lamp_production": "Produksi LAMP ASSY",
    "smt_stock": "Stock SMT",
    "production_needs": "Kebutuhan vs Stock",
    "variance": "Variance Stock",
    "users": "Manajemen User",
}
LEVELS = ["none", "read", "write"]
LEVEL_LABELS = {"none": "Tidak ada", "read": "Lihat", "write": "Ubah"}

ROLE_DEFAULT_PERMS = {
    "admin": {m: "write" for m in MODULES},
    "management": {**{m: "write" for m in MODULES}, "users": "none"},
    "production_planning": {"smt_production": "read", "lamp_production": "read", "smt_stock": "write",
                            "production_needs": "write", "variance": "write", "users": "none"},
    "production_control": {"smt_production": "write", "lamp_production": "write", "smt_stock": "read",
                           "production_needs": "read", "variance": "write", "users": "none"},
    "smt": {"smt_production": "write", "lamp_production": "read", "smt_stock": "write",
            "production_needs": "read", "variance": "read", "users": "none"},
    "assembly": {"smt_production": "read", "lamp_production": "write", "smt_stock": "read",
                 "production_needs": "read", "variance": "read", "users": "none"},
}


def effective_perms(user: dict) -> Dict[str, str]:
    base = dict(ROLE_DEFAULT_PERMS.get(user.get("role"), {}))
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
        return float(v)
    except Exception:
        return default


def r1(v):
    return round(v, 2)


# ---------------------------------------------------------------------------
# Field definitions (sesuai kolom Excel DATA STOCK) & rumus
# ---------------------------------------------------------------------------
BASE_FIELDS = [("date", "Tanggal", False), ("lane", "Lane", False), ("type", "Type", False), ("ics_no", "ICS No.", False)]

FIELDS = {
    "smt_production": BASE_FIELDS + [
        ("tt", "T/T (detik)", True), ("led_rank", "LED Rank", False),
        ("smt1", "SMT Shift 1", True), ("smt2", "SMT Shift 2", True), ("smt3", "SMT Shift 3", True)],
    "lamp_production": BASE_FIELDS + [
        ("plan_assy", "Plan Assy", True), ("assy1", "Assy Shift 1", True), ("assy2", "Assy Shift 2", True),
        ("assy3", "Assy Shift 3", True), ("stock_ok_prev", "Stock OK SMT Kemarin", True)],
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
}


def compute_smt_production(d: dict) -> dict:
    tt = num(d.get("tt"))
    d["cap_h"] = r1(3600 / tt) if tt else 0.0
    d["total"] = r1(num(d.get("smt1")) + num(d.get("smt2")) + num(d.get("smt3")))
    return d


def compute_lamp_production(d: dict) -> dict:
    plan = num(d.get("plan_assy"))
    d["total"] = r1(num(d.get("assy1")) + num(d.get("assy2")) + num(d.get("assy3")))
    d["blc"] = r1(num(d.get("stock_ok_prev")) - plan)
    d["achievement"] = round(d["total"] / plan * 100, 1) if plan else 0.0
    d["status"] = "SELESAI" if plan and d["total"] >= plan else ("PROSES" if d["total"] > 0 else "BELUM MULAI")
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
    "lamp-production": {"module": "lamp_production", "compute": compute_lamp_production, "sort": [("date", -1), ("lane", 1)]},
    "smt-stock": {"module": "smt_stock", "compute": compute_smt_stock, "sort": [("date", -1), ("lane", 1)]},
    "production-needs": {"module": "production_needs", "compute": compute_needs, "sort": [("date", -1), ("lane", 1)]},
    "variance": {"module": "variance", "compute": compute_variance, "sort": [("date", -1), ("lane", 1)]},
}


def normalize(module: str, body: dict) -> dict:
    d = {}
    for key, _label, is_num in FIELDS[module]:
        v = body.get(key)
        d[key] = num(v) if is_num else ("" if v is None else str(v).strip())
    if module == "smt_stock" or module == "variance":
        d["reason"] = str(body.get("reason") or "")
    return DATASETS[[k for k, v in DATASETS.items() if v["module"] == module][0]]["compute"](d)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginBody(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str
    permissions: Optional[Dict[str, str]] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    permissions: Optional[Dict[str, str]] = None


def set_cookie(resp: Response, token: str):
    resp.set_cookie(key="access_token", value=token, httponly=True, secure=True,
                    samesite="none", max_age=604800, path="/")


@api.post("/auth/login")
async def login(body: LoginBody, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    token = create_access_token(str(user["_id"]), email)
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
    email = body.email.lower()
    if body.role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail="Role tidak valid")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    doc = {"email": email, "password_hash": hash_password(body.password), "name": body.name.strip(),
           "role": body.role, "permissions": validate_perms(body.permissions),
           "created_at": datetime.now(timezone.utc).isoformat()}
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return public_user(doc)


@api.put("/users/{uid}")
async def update_user(uid: str, body: UserUpdate, user: dict = Depends(require_perm("users", "write"))):
    target = await db.users.find_one({"_id": oid(uid)})
    if not target:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    is_main_admin = target.get("email") == os.environ.get("ADMIN_EMAIL", "").lower()
    upd = {}
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
    if upd:
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.users.update_one({"_id": oid(uid)}, {"$set": upd})
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
    async def create_item(body: dict, user: dict = Depends(require_perm(module, "write"))):
        d = normalize(module, body)
        if not d.get("date") or not d.get("ics_no"):
            raise HTTPException(status_code=400, detail="Tanggal dan ICS No. wajib diisi")
        d["created_at"] = datetime.now(timezone.utc).isoformat()
        res = await coll.insert_one(d)
        d["id"] = str(res.inserted_id); d.pop("_id", None)
        return d

    @api.put(f"/{dataset}/{{rid}}")
    async def update_item(rid: str, body: dict, user: dict = Depends(require_perm(module, "write"))):
        d = normalize(module, body)
        d["updated_at"] = datetime.now(timezone.utc).isoformat()
        await coll.update_one({"_id": oid(rid)}, {"$set": d})
        doc = await coll.find_one({"_id": oid(rid)})
        if not doc:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        return clean(doc)

    @api.delete(f"/{dataset}/{{rid}}")
    async def delete_item(rid: str, user: dict = Depends(require_perm(module, "write"))):
        await coll.delete_one({"_id": oid(rid)})
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
    for m in ("smt_production", "lamp_production", "smt_stock", "production_needs", "variance"):
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
    lamp = await db.lamp_production.find(dq).to_list(10000)
    needs = await db.production_needs.find(dq).to_list(10000)
    var = await db.variance.find(dq).to_list(10000)

    stock_dates = await db.smt_stock.distinct("date", dq)
    stock = await db.smt_stock.find({"date": max(stock_dates)}).to_list(10000) if stock_dates else []

    smt_total = sum(num(x.get("total")) for x in smt)
    plan_assy = sum(num(x.get("plan_assy")) for x in lamp)
    assy_total = sum(num(x.get("total")) for x in lamp)
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
        t = by_lane.setdefault(x.get("lane") or "-", {"lane": x.get("lane") or "-", "smt1": 0, "smt2": 0, "smt3": 0})
        for s in ("smt1", "smt2", "smt3"):
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
            "smt_total": smt_total, "smt_items": len(smt),
            "plan_assy": plan_assy, "assy_total": assy_total,
            "assy_achievement": round(assy_total / plan_assy * 100, 1) if plan_assy else 0.0,
            "stock_ok": stock_ok, "stock_total": stock_total, "stock_items": len(stock),
            "stock_date": max(stock_dates) if stock_dates else None,
            "shortage_count": len(shortage_items), "needs_items": len(needs),
            "variance_count": len(variance_items), "variance_items": len(var),
            "variance_sum": sum(num(v.get("variance")) for v in var),
        },
        "stock_breakdown": stock_breakdown,
        "smt_trend": trend(smt, {"total": "total"}),
        "assy_trend": trend(lamp, {"plan": "plan_assy", "actual": "total"}),
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
    return m


def parse_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        dff = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    else:
        dff = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    dff = dff.dropna(how="all")
    return dff.where(pd.notnull(dff), None)


def map_rows(module: str, dff: pd.DataFrame):
    hm = header_map(module)
    cols = {c: hm.get(str(c).strip().lower()) for c in dff.columns}
    unknown = [c for c, k in cols.items() if k is None]
    rows = []
    for rec in dff.to_dict(orient="records"):
        r = {}
        for c, k in cols.items():
            if k:
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
    invalid = sum(1 for r in rows if not r.get("date") or not r.get("ics_no"))
    columns = [k for k, _, _ in FIELDS[module]] + [k for k in rows[0].keys() if rows and k not in [f[0] for f in FIELDS[module]]] if rows else []
    return {"columns": columns, "rows": rows[:100], "total": len(rows), "invalid": invalid, "unknown_columns": unknown}


@api.post("/import/{dataset}/confirm")
async def import_confirm(dataset: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
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
    for r in rows:
        if not r.get("date") or not r.get("ics_no"):
            skipped += 1
            continue
        key = {"date": r["date"], "ics_no": r["ics_no"]}
        existing = await db[module].find_one(key)
        if existing:
            r["updated_at"] = now
            await db[module].update_one(key, {"$set": r}); updated += 1
        else:
            r["created_at"] = now
            await db[module].insert_one(r); inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


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
SEED_VERSION = 2


async def seed_admin():
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({"email": email, "password_hash": hash_password(password),
                                   "name": "Admin Utama", "role": "admin", "permissions": {},
                                   "created_at": datetime.now(timezone.utc).isoformat()})
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


async def seed_demo_users():
    demos = [
        ("ppic@cds.co.id", "PPIC Andi", "production_planning"),
        ("pc@cds.co.id", "PC Budi", "production_control"),
        ("smt@cds.co.id", "SMT Citra", "smt"),
        ("assy@cds.co.id", "Assy Dewi", "assembly"),
        ("manager@cds.co.id", "Manager Eko", "management"),
    ]
    for email, name, role in demos:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({"email": email, "password_hash": hash_password("password123"),
                                       "name": name, "role": role, "permissions": {},
                                       "created_at": datetime.now(timezone.utc).isoformat()})


async def seed_from_excel():
    meta = await db.meta.find_one({"_id": "seed"})
    if meta and meta.get("version") == SEED_VERSION:
        return
    path = ROOT_DIR / "seed" / "data_stock.json"
    if not path.exists():
        return
    rows = json.loads(path.read_text())
    prod_date, stock_date = "2026-09-12", "2026-09-13"
    now = datetime.now(timezone.utc).isoformat()
    payload = {cfg["module"]: [] for cfg in DATASETS.values()}
    for r in rows:
        base = {"lane": r["lane"], "type": r["type"], "ics_no": r["ics_no"]}
        smt = normalize("smt_production", {**base, "date": prod_date, "tt": r["tt"], "led_rank": r["led_rank"],
                                           "smt1": r["smt1"], "smt2": r["smt2"], "smt3": r["smt3"]})
        lamp = normalize("lamp_production", {**base, "date": prod_date, "plan_assy": r["plan_assy"], "assy1": r["assy1"],
                                             "assy2": r["assy2"], "assy3": r["assy3"], "stock_ok_prev": r["stock_ok_prev"]})
        stock = normalize("smt_stock", {**base, "date": stock_date, "stock_ok_prev": r["stock_ok_prev"], "coating": r["coating"],
                                        "belum_cutting": r["belum_cutting"], "belum_ict": r["belum_ict"],
                                        "belum_fct": r["belum_fct"], "ok": r["ok"], "tray": r["tray"]})
        needs = normalize("production_needs", {**base, "date": prod_date, "plan_assy": r["plan_assy"], "stock_ok_prev": r["stock_ok_prev"]})
        var = normalize("variance", {**base, "date": stock_date, "total_stock_prev": r["total_stock_prev"],
                                     "smt_total": smt["total"], "assy_total": lamp["total"], "smt3": r["smt3"],
                                     "assy3": r["assy3"], "actual_total_stock": stock["total"]})
        for m, d in (("smt_production", smt), ("lamp_production", lamp), ("smt_stock", stock),
                     ("production_needs", needs), ("variance", var)):
            d["created_at"] = now
            payload[m].append(d)
    for m, docs in payload.items():
        await db[m].delete_many({})
        if docs:
            await db[m].insert_many(docs)
        await db[m].create_index([("date", -1), ("ics_no", 1)])
    await db.meta.update_one({"_id": "seed"}, {"$set": {"version": SEED_VERSION, "at": now}}, upsert=True)
    logger.info("Seeded %d items from DATA STOCK.xlsx", len(rows))


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await seed_admin()
    await seed_demo_users()
    await seed_from_excel()


@app.on_event("shutdown")
async def shutdown():
    client.close()
