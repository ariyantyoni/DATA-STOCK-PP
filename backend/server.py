from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, BeforeValidator, ConfigDict
from typing import List, Optional, Annotated
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging
import io
import jwt
import bcrypt
import pandas as pd

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
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
# Helpers: Mongo model base
# ---------------------------------------------------------------------------
PyObjectId = Annotated[str, BeforeValidator(str)]

ROLE_LABELS = {
    "admin": "Administrator",
    "management": "Management",
    "production_planning": "Production Planning (PPIC)",
    "production_control": "Production Control (PC)",
    "smt": "SMT",
    "assembly": "Assembly (LAMP ASSY)",
}

WRITE_ROLES = {
    "smt_production": {"admin", "management", "production_control", "smt"},
    "lamp_production": {"admin", "management", "production_control", "assembly"},
    "smt_stock": {"admin", "management", "production_planning", "smt"},
    "production_needs": {"admin", "management", "production_planning"},
    "variance": {"admin", "management", "production_planning", "production_control"},
    "users": {"admin"},
}


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
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User tidak ditemukan")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")


def require_write(module: str):
    async def dep(user: dict = Depends(get_current_user)):
        if user["role"] not in WRITE_ROLES.get(module, set()):
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk mengubah data ini")
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


# ---------------------------------------------------------------------------
# Calculation logic
# ---------------------------------------------------------------------------
def compute_smt_production(d: dict) -> dict:
    target = num(d.get("target"))
    actual = num(d.get("actual"))
    defect = num(d.get("defect"))
    good = max(actual - defect, 0)
    d["good"] = good
    d["achievement"] = round((actual / target * 100), 1) if target else 0.0
    d["yield_rate"] = round((good / actual * 100), 1) if actual else 0.0
    d["balance"] = round(actual - target, 1)
    return d


def compute_lamp_production(d: dict) -> dict:
    target = num(d.get("target"))
    actual = num(d.get("actual"))
    d["achievement"] = round((actual / target * 100), 1) if target else 0.0
    d["balance"] = round(actual - target, 1)
    d["status"] = "SELESAI" if actual >= target and target > 0 else ("PROSES" if actual > 0 else "BELUM MULAI")
    return d


def compute_stock_status(actual, safety, reorder) -> str:
    actual = num(actual); safety = num(safety); reorder = num(reorder)
    if actual < safety:
        return "CRITICAL"
    if actual < reorder:
        return "REORDER"
    return "AMAN"


def compute_smt_stock(d: dict) -> dict:
    d["status"] = compute_stock_status(d.get("actual_stock"), d.get("safety_stock"), d.get("reorder_level"))
    return d


def compute_variance(d: dict) -> dict:
    system_stock = num(d.get("system_stock"))
    physical_stock = num(d.get("physical_stock"))
    var = physical_stock - system_stock
    d["variance"] = round(var, 2)
    d["variance_pct"] = round((var / system_stock * 100), 2) if system_stock else 0.0
    d["accuracy"] = round(max(0.0, 100 - abs(d["variance_pct"])), 2)
    d["variance_status"] = "OK" if var == 0 else ("SURPLUS" if var > 0 else "SHORTAGE")
    return d


# ---------------------------------------------------------------------------
# Auth models & routes
# ---------------------------------------------------------------------------
class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str


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
    return {"token": token, "user": {"id": str(user["_id"]), "email": email,
            "name": user["name"], "role": user["role"], "role_label": ROLE_LABELS.get(user["role"], user["role"])}}


@api.post("/auth/register")
async def register(body: RegisterBody, user: dict = Depends(require_write("users"))):
    email = body.email.lower()
    if body.role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail="Role tidak valid")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    doc = {"email": email, "password_hash": hash_password(body.password), "name": body.name,
           "role": body.role, "created_at": datetime.now(timezone.utc).isoformat()}
    res = await db.users.insert_one(doc)
    return {"id": str(res.inserted_id), "email": email, "name": body.name, "role": body.role,
            "role_label": ROLE_LABELS.get(body.role)}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    user["role_label"] = ROLE_LABELS.get(user["role"], user["role"])
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    docs = await db.users.find({}, {"password_hash": 0}).sort("created_at", -1).to_list(500)
    out = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d["role_label"] = ROLE_LABELS.get(d.get("role"), d.get("role"))
        out.append(d)
    return out


@api.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_write("users"))):
    target = await db.users.find_one({"_id": oid(uid)})
    if target and target.get("email") == os.environ.get("ADMIN_EMAIL", "").lower():
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun admin utama")
    await db.users.delete_one({"_id": oid(uid)})
    return {"ok": True}


@api.get("/roles")
async def get_roles(user: dict = Depends(get_current_user)):
    return [{"value": k, "label": v} for k, v in ROLE_LABELS.items() if k != "admin"]


# ---------------------------------------------------------------------------
# Generic filter builder
# ---------------------------------------------------------------------------
def build_query(date_from, date_to, lane, type_, part_number, status, shift, search):
    q = {}
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        q["date"] = rng
    if lane:
        q["lane"] = lane
    if type_:
        q["type"] = type_
    if part_number:
        q["part_number"] = part_number
    if status:
        q["status"] = status
    if shift:
        q["shift"] = shift
    if search:
        q["$or"] = [
            {"part_number": {"$regex": search, "$options": "i"}},
            {"type": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"lane": {"$regex": search, "$options": "i"}},
        ]
    return q


# ---------------------------------------------------------------------------
# SMT PRODUCTION
# ---------------------------------------------------------------------------
@api.get("/smt-production")
async def get_smt_production(date_from: Optional[str] = None, date_to: Optional[str] = None,
                             lane: Optional[str] = None, type: Optional[str] = None,
                             part_number: Optional[str] = None, shift: Optional[str] = None,
                             search: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = build_query(date_from, date_to, lane, type, part_number, None, shift, search)
    docs = await db.smt_production.find(q).sort("date", -1).to_list(2000)
    return [clean(d) for d in docs]


@api.post("/smt-production")
async def create_smt_production(body: dict, user: dict = Depends(require_write("smt_production"))):
    d = compute_smt_production(dict(body))
    d["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.smt_production.insert_one(d)
    d["id"] = str(res.inserted_id); d.pop("_id", None)
    return d


@api.put("/smt-production/{rid}")
async def update_smt_production(rid: str, body: dict, user: dict = Depends(require_write("smt_production"))):
    d = compute_smt_production(dict(body))
    d.pop("id", None); d.pop("_id", None)
    await db.smt_production.update_one({"_id": oid(rid)}, {"$set": d})
    doc = await db.smt_production.find_one({"_id": oid(rid)})
    return clean(doc)


@api.delete("/smt-production/{rid}")
async def delete_smt_production(rid: str, user: dict = Depends(require_write("smt_production"))):
    await db.smt_production.delete_one({"_id": oid(rid)})
    return {"ok": True}


# ---------------------------------------------------------------------------
# LAMP ASSY PRODUCTION
# ---------------------------------------------------------------------------
@api.get("/lamp-production")
async def get_lamp_production(date_from: Optional[str] = None, date_to: Optional[str] = None,
                              lane: Optional[str] = None, type: Optional[str] = None,
                              part_number: Optional[str] = None, shift: Optional[str] = None,
                              status: Optional[str] = None, search: Optional[str] = None,
                              user: dict = Depends(get_current_user)):
    q = build_query(date_from, date_to, lane, type, part_number, status, shift, search)
    docs = await db.lamp_production.find(q).sort("date", -1).to_list(2000)
    return [clean(d) for d in docs]


@api.post("/lamp-production")
async def create_lamp_production(body: dict, user: dict = Depends(require_write("lamp_production"))):
    d = compute_lamp_production(dict(body))
    d["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.lamp_production.insert_one(d)
    d["id"] = str(res.inserted_id); d.pop("_id", None)
    return d


@api.put("/lamp-production/{rid}")
async def update_lamp_production(rid: str, body: dict, user: dict = Depends(require_write("lamp_production"))):
    d = compute_lamp_production(dict(body))
    d.pop("id", None); d.pop("_id", None)
    await db.lamp_production.update_one({"_id": oid(rid)}, {"$set": d})
    doc = await db.lamp_production.find_one({"_id": oid(rid)})
    return clean(doc)


@api.delete("/lamp-production/{rid}")
async def delete_lamp_production(rid: str, user: dict = Depends(require_write("lamp_production"))):
    await db.lamp_production.delete_one({"_id": oid(rid)})
    return {"ok": True}


# ---------------------------------------------------------------------------
# SMT STOCK
# ---------------------------------------------------------------------------
@api.get("/smt-stock")
async def get_smt_stock(type: Optional[str] = None, part_number: Optional[str] = None,
                        status: Optional[str] = None, search: Optional[str] = None,
                        user: dict = Depends(get_current_user)):
    q = build_query(None, None, None, type, part_number, status, None, search)
    docs = await db.smt_stock.find(q).sort("part_number", 1).to_list(3000)
    return [clean(d) for d in docs]


@api.post("/smt-stock")
async def create_smt_stock(body: dict, user: dict = Depends(require_write("smt_stock"))):
    d = compute_smt_stock(dict(body))
    d["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.smt_stock.insert_one(d)
    d["id"] = str(res.inserted_id); d.pop("_id", None)
    return d


@api.put("/smt-stock/{rid}")
async def update_smt_stock(rid: str, body: dict, user: dict = Depends(require_write("smt_stock"))):
    d = compute_smt_stock(dict(body))
    d.pop("id", None); d.pop("_id", None)
    d["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.smt_stock.update_one({"_id": oid(rid)}, {"$set": d})
    doc = await db.smt_stock.find_one({"_id": oid(rid)})
    return clean(doc)


@api.delete("/smt-stock/{rid}")
async def delete_smt_stock(rid: str, user: dict = Depends(require_write("smt_stock"))):
    await db.smt_stock.delete_one({"_id": oid(rid)})
    return {"ok": True}


# ---------------------------------------------------------------------------
# PRODUCTION NEEDS vs STOCK (Shortage control)
# ---------------------------------------------------------------------------
async def enrich_needs(docs):
    stocks = await db.smt_stock.find({}).to_list(3000)
    stock_map = {s["part_number"]: num(s.get("actual_stock")) for s in stocks}
    out = []
    for d in docs:
        dd = clean(d)
        required = num(dd.get("required_qty"))
        stock_actual = stock_map.get(dd.get("part_number"), 0.0)
        dd["stock_actual"] = stock_actual
        bal = stock_actual - required
        dd["balance"] = round(bal, 2)
        dd["shortage_qty"] = round(abs(bal), 2) if bal < 0 else 0.0
        dd["fulfillment"] = round((stock_actual / required * 100), 1) if required else 100.0
        dd["status"] = "SHORTAGE" if bal < 0 else ("PAS" if bal == 0 else "CUKUP")
        out.append(dd)
    return out


@api.get("/production-needs")
async def get_production_needs(date_from: Optional[str] = None, date_to: Optional[str] = None,
                               type: Optional[str] = None, part_number: Optional[str] = None,
                               status: Optional[str] = None, search: Optional[str] = None,
                               user: dict = Depends(get_current_user)):
    q = build_query(date_from, date_to, None, type, part_number, None, None, search)
    docs = await db.production_needs.find(q).sort("date", -1).to_list(3000)
    enriched = await enrich_needs(docs)
    if status:
        enriched = [e for e in enriched if e["status"] == status]
    return enriched


@api.post("/production-needs")
async def create_production_needs(body: dict, user: dict = Depends(require_write("production_needs"))):
    d = dict(body)
    d["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.production_needs.insert_one(d)
    doc = await db.production_needs.find_one({"_id": res.inserted_id})
    return (await enrich_needs([doc]))[0]


@api.put("/production-needs/{rid}")
async def update_production_needs(rid: str, body: dict, user: dict = Depends(require_write("production_needs"))):
    d = dict(body); d.pop("id", None); d.pop("_id", None)
    await db.production_needs.update_one({"_id": oid(rid)}, {"$set": d})
    doc = await db.production_needs.find_one({"_id": oid(rid)})
    return (await enrich_needs([doc]))[0]


@api.delete("/production-needs/{rid}")
async def delete_production_needs(rid: str, user: dict = Depends(require_write("production_needs"))):
    await db.production_needs.delete_one({"_id": oid(rid)})
    return {"ok": True}


# ---------------------------------------------------------------------------
# VARIANCE
# ---------------------------------------------------------------------------
@api.get("/variance")
async def get_variance(date_from: Optional[str] = None, date_to: Optional[str] = None,
                       type: Optional[str] = None, part_number: Optional[str] = None,
                       status: Optional[str] = None, search: Optional[str] = None,
                       user: dict = Depends(get_current_user)):
    q = build_query(date_from, date_to, None, type, part_number, None, None, search)
    docs = await db.variance.find(q).sort("date", -1).to_list(3000)
    out = [clean(d) for d in docs]
    if status:
        out = [o for o in out if o.get("variance_status") == status]
    return out


@api.post("/variance")
async def create_variance(body: dict, user: dict = Depends(require_write("variance"))):
    d = compute_variance(dict(body))
    d["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.variance.insert_one(d)
    d["id"] = str(res.inserted_id); d.pop("_id", None)
    return d


@api.put("/variance/{rid}")
async def update_variance(rid: str, body: dict, user: dict = Depends(require_write("variance"))):
    d = compute_variance(dict(body)); d.pop("id", None); d.pop("_id", None)
    await db.variance.update_one({"_id": oid(rid)}, {"$set": d})
    doc = await db.variance.find_one({"_id": oid(rid)})
    return clean(doc)


@api.delete("/variance/{rid}")
async def delete_variance(rid: str, user: dict = Depends(require_write("variance"))):
    await db.variance.delete_one({"_id": oid(rid)})
    return {"ok": True}


# ---------------------------------------------------------------------------
# META options for filters
# ---------------------------------------------------------------------------
@api.get("/meta/options")
async def meta_options(user: dict = Depends(get_current_user)):
    lanes = sorted({x for x in await db.smt_production.distinct("lane") if x})
    types = sorted({x for x in (await db.smt_production.distinct("type") +
                    await db.smt_stock.distinct("type") +
                    await db.lamp_production.distinct("type")) if x})
    parts = sorted({x for x in (await db.smt_stock.distinct("part_number") +
                    await db.smt_production.distinct("part_number")) if x})
    lamp_lines = sorted({x for x in await db.lamp_production.distinct("lane") if x})
    return {"lanes": lanes, "types": types, "part_numbers": parts, "lamp_lines": lamp_lines,
            "shifts": ["Shift 1", "Shift 2", "Shift 3"],
            "stock_status": ["AMAN", "REORDER", "CRITICAL"],
            "needs_status": ["CUKUP", "PAS", "SHORTAGE"],
            "variance_status": ["OK", "SURPLUS", "SHORTAGE"]}


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@api.get("/dashboard/summary")
async def dashboard_summary(date_from: Optional[str] = None, date_to: Optional[str] = None,
                            user: dict = Depends(get_current_user)):
    dq = {}
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        dq["date"] = rng

    smt = await db.smt_production.find(dq).to_list(5000)
    lamp = await db.lamp_production.find(dq).to_list(5000)
    stock = await db.smt_stock.find({}).to_list(5000)
    needs_docs = await db.production_needs.find(dq).to_list(5000)
    needs = await enrich_needs(needs_docs)
    var = await db.variance.find(dq).to_list(5000)

    smt_target = sum(num(x.get("target")) for x in smt)
    smt_actual = sum(num(x.get("actual")) for x in smt)
    smt_defect = sum(num(x.get("defect")) for x in smt)
    lamp_target = sum(num(x.get("target")) for x in lamp)
    lamp_actual = sum(num(x.get("actual")) for x in lamp)

    stock_critical = sum(1 for s in stock if compute_stock_status(s.get("actual_stock"), s.get("safety_stock"), s.get("reorder_level")) == "CRITICAL")
    stock_reorder = sum(1 for s in stock if compute_stock_status(s.get("actual_stock"), s.get("safety_stock"), s.get("reorder_level")) == "REORDER")
    stock_aman = len(stock) - stock_critical - stock_reorder

    shortage_items = [n for n in needs if n["status"] == "SHORTAGE"]
    variance_items = [v for v in var if num(v.get("variance")) != 0]
    accuracy = round(sum(num(v.get("accuracy")) for v in var) / len(var), 1) if var else 100.0

    # SMT production trend by date
    trend = {}
    for x in smt:
        d = x.get("date", "")
        t = trend.setdefault(d, {"date": d, "target": 0, "actual": 0, "defect": 0})
        t["target"] += num(x.get("target")); t["actual"] += num(x.get("actual")); t["defect"] += num(x.get("defect"))
    smt_trend = sorted(trend.values(), key=lambda r: r["date"])[-14:]

    lamp_trend_map = {}
    for x in lamp:
        d = x.get("date", "")
        t = lamp_trend_map.setdefault(d, {"date": d, "target": 0, "actual": 0})
        t["target"] += num(x.get("target")); t["actual"] += num(x.get("actual"))
    lamp_trend = sorted(lamp_trend_map.values(), key=lambda r: r["date"])[-14:]

    # top shortage
    top_shortage = sorted(shortage_items, key=lambda n: n["shortage_qty"], reverse=True)[:6]

    return {
        "kpi": {
            "smt_target": smt_target, "smt_actual": smt_actual, "smt_defect": smt_defect,
            "smt_achievement": round((smt_actual / smt_target * 100), 1) if smt_target else 0.0,
            "smt_yield": round(((smt_actual - smt_defect) / smt_actual * 100), 1) if smt_actual else 0.0,
            "lamp_target": lamp_target, "lamp_actual": lamp_actual,
            "lamp_achievement": round((lamp_actual / lamp_target * 100), 1) if lamp_target else 0.0,
            "shortage_count": len(shortage_items),
            "variance_count": len(variance_items),
            "stock_accuracy": accuracy,
            "stock_total": len(stock),
        },
        "stock_status": [
            {"name": "AMAN", "value": stock_aman},
            {"name": "REORDER", "value": stock_reorder},
            {"name": "CRITICAL", "value": stock_critical},
        ],
        "smt_trend": smt_trend,
        "lamp_trend": lamp_trend,
        "top_shortage": top_shortage,
    }


# ---------------------------------------------------------------------------
# EXCEL / CSV IMPORT
# ---------------------------------------------------------------------------
IMPORT_MAP = {
    "smt-production": {"collection": "smt_production", "module": "smt_production", "compute": compute_smt_production},
    "lamp-production": {"collection": "lamp_production", "module": "lamp_production", "compute": compute_lamp_production},
    "smt-stock": {"collection": "smt_stock", "module": "smt_stock", "compute": compute_smt_stock},
    "production-needs": {"collection": "production_needs", "module": "production_needs", "compute": None},
    "variance": {"collection": "variance", "module": "variance", "compute": compute_variance},
}

NUMERIC_FIELDS = {"target", "actual", "defect", "actual_stock", "safety_stock", "reorder_level",
                  "required_qty", "system_stock", "physical_stock"}


def parse_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes))
    return pd.read_excel(io.BytesIO(file_bytes))


@api.post("/import/{dataset}/preview")
async def import_preview(dataset: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if dataset not in IMPORT_MAP:
        raise HTTPException(status_code=400, detail="Dataset tidak dikenal")
    content = await file.read()
    try:
        dff = parse_dataframe(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {e}")
    dff = dff.where(pd.notnull(dff), None)
    rows = dff.to_dict(orient="records")
    return {"columns": list(dff.columns), "rows": rows[:100], "total": len(rows)}


@api.post("/import/{dataset}/confirm")
async def import_confirm(dataset: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if dataset not in IMPORT_MAP:
        raise HTTPException(status_code=400, detail="Dataset tidak dikenal")
    cfg = IMPORT_MAP[dataset]
    if user["role"] not in WRITE_ROLES.get(cfg["module"], set()):
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses import untuk data ini")
    content = await file.read()
    try:
        dff = parse_dataframe(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file: {e}")
    dff = dff.where(pd.notnull(dff), None)
    rows = dff.to_dict(orient="records")
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r = {str(k).strip(): v for k, v in r.items()}
        for f in NUMERIC_FIELDS:
            if f in r:
                r[f] = num(r[f])
        if cfg["compute"]:
            r = cfg["compute"](r)
        r["created_at"] = now
        await db[cfg["collection"]].insert_one(r)
        inserted += 1
    return {"inserted": inserted}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup: indexes, admin seed, sample data
# ---------------------------------------------------------------------------
async def seed_admin():
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": email})
    if existing is None:
        await db.users.insert_one({"email": email, "password_hash": hash_password(password),
                                   "name": "Admin Utama", "role": "admin",
                                   "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info("Admin seeded")
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
                                       "name": name, "role": role,
                                       "created_at": datetime.now(timezone.utc).isoformat()})


async def seed_sample_data():
    if await db.smt_production.count_documents({}) > 0:
        return
    from datetime import date
    today = date.today()
    lanes = ["Lane 1", "Lane 2", "Lane 3", "Lane 4"]
    types = ["HL- ADV150", "TL-BEAT", "HL-VARIO160", "DRL-PCX160"]
    parts = ["CHIP-R0402-10K", "CHIP-C0603-100N", "LED-3528-W", "IC-DRV-8871", "CONN-04P-JST", "DIODE-SS14"]

    smt_rows = []
    import random
    for i in range(14):
        d = (today - timedelta(days=13 - i)).isoformat()
        for lane in lanes:
            for shift in ["Shift 1", "Shift 2"]:
                target = random.choice([1200, 1500, 1800, 2000])
                actual = target - random.randint(-150, 250)
                defect = random.randint(2, 40)
                row = compute_smt_production({
                    "date": d, "lane": lane, "shift": shift,
                    "part_number": random.choice(parts), "type": random.choice(types),
                    "target": target, "actual": actual, "defect": defect,
                    "created_at": datetime.now(timezone.utc).isoformat()})
                smt_rows.append(row)
    await db.smt_production.insert_many(smt_rows)

    lamp_lines = ["Head Lamp Line A", "Tail Lamp Line B", "DRL Line C"]
    lamp_types = ["HL-ADV150", "TL-BEAT", "DRL-PCX160"]
    lamp_rows = []
    for i in range(14):
        d = (today - timedelta(days=13 - i)).isoformat()
        for line, tp in zip(lamp_lines, lamp_types):
            target = random.choice([400, 500, 600])
            actual = target - random.randint(-50, 80)
            lamp_rows.append(compute_lamp_production({
                "date": d, "lane": line, "type": tp, "shift": "Shift 1",
                "part_number": tp, "target": target, "actual": actual,
                "created_at": datetime.now(timezone.utc).isoformat()}))
    await db.lamp_production.insert_many(lamp_rows)

    stock_rows = []
    descs = {"CHIP-R0402-10K": "Resistor 0402 10K Ohm", "CHIP-C0603-100N": "Capacitor 0603 100nF",
             "LED-3528-W": "LED SMD 3528 White", "IC-DRV-8871": "Motor Driver IC DRV8871",
             "CONN-04P-JST": "Connector JST 4 Pin", "DIODE-SS14": "Schottky Diode SS14"}
    stock_vals = [
        ("CHIP-R0402-10K", 250000, 80000, 120000, "Reel"),
        ("CHIP-C0603-100N", 45000, 60000, 90000, "Reel"),
        ("LED-3528-W", 15000, 20000, 35000, "Reel"),
        ("IC-DRV-8871", 8500, 5000, 8000, "Tray"),
        ("CONN-04P-JST", 3200, 4000, 7000, "Tray"),
        ("DIODE-SS14", 90000, 30000, 50000, "Reel"),
    ]
    for pn, actual, safety, reorder, unit in stock_vals:
        stock_rows.append(compute_smt_stock({
            "part_number": pn, "description": descs[pn], "type": "Component", "unit": unit,
            "actual_stock": actual, "safety_stock": safety, "reorder_level": reorder,
            "updated_at": datetime.now(timezone.utc).isoformat()}))
    await db.smt_stock.insert_many(stock_rows)

    needs_rows = []
    needs_vals = [("CHIP-R0402-10K", 180000), ("CHIP-C0603-100N", 70000), ("LED-3528-W", 22000),
                  ("IC-DRV-8871", 6000), ("CONN-04P-JST", 5000), ("DIODE-SS14", 40000)]
    for pn, req in needs_vals:
        needs_rows.append({"date": today.isoformat(), "part_number": pn, "type": "Component",
                           "model": "MPS Mingguan", "required_qty": req,
                           "created_at": datetime.now(timezone.utc).isoformat()})
    await db.production_needs.insert_many(needs_rows)

    var_rows = []
    var_vals = [("CHIP-R0402-10K", 250000, 249200), ("CHIP-C0603-100N", 45000, 45000),
                ("LED-3528-W", 15000, 14550), ("IC-DRV-8871", 8500, 8620),
                ("CONN-04P-JST", 3200, 3150), ("DIODE-SS14", 90000, 89000)]
    for pn, sys_s, phys in var_vals:
        var_rows.append(compute_variance({"date": today.isoformat(), "part_number": pn, "type": "Component",
                        "system_stock": sys_s, "physical_stock": phys, "reason": "",
                        "created_at": datetime.now(timezone.utc).isoformat()}))
    await db.variance.insert_many(var_rows)
    logger.info("Sample data seeded")


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await seed_admin()
    await seed_demo_users()
    await seed_sample_data()


@app.on_event("shutdown")
async def shutdown():
    client.close()
