# Iteration 8: Kebutuhan Assy VS. Stock Part Production grid (needs-grid) + smt-stock cell editing
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DATE = "2030-01-15"
ICS_A, TYPE_A = "9900000081", "ZT ALPHA"
ICS_B, TYPE_B = "9900000082", "ZT BETA"

mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "part_production")]


def login(u, p):
    r = requests.post(f"{API}/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s = requests.Session()
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    s.cookies.update(r.cookies)
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin", "admin123")


@pytest.fixture(scope="module")
def assy():
    return login("assy", "password123")


@pytest.fixture(scope="module")
def seed(admin):
    base = {"lane": "ZT9", "product": "REGULER", "proses_mesin": "INJECTION", "group": "GROUP 1", "tt_assy": 36, "material_per_unit": 1}
    a = admin.post(f"{API}/items", json={**base, "ics_no": ICS_A, "type": TYPE_A, "ics_name": "ZT ITEM A", "std_stock_min": 0, "std_stock_max": 20})
    b = admin.post(f"{API}/items", json={**base, "ics_no": ICS_B, "type": TYPE_B, "ics_name": "ZT ITEM B"})
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    stk = {}
    for sh, g1 in (("SHIFT 3", 30), ("SHIFT 1", 1000), ("SHIFT 2", 2000)):
        r = admin.post(f"{API}/smt-stock", json={"date": DATE, "shift": sh, "lane": "ZT9", "product": "REGULER", "type": TYPE_A,
                                                    "ics_no": ICS_A, "group1": g1, "group2": 5, "part_ragu": 5})
        assert r.status_code == 200, r.text
        stk[sh] = r.json()["id"]
    yield {"a": a.json(), "b": b.json(), "stk": stk}
    # cleanup
    mongo.smt_stock.delete_many({"ics_no": {"$in": [ICS_A, ICS_B]}})
    mongo.needs_entries.delete_many({"ics_no": {"$in": [ICS_A, ICS_B]}})
    mongo.items.delete_many({"ics_no": {"$in": [ICS_A, ICS_B]}})


def grid_row(admin, ics, typ, date=DATE):
    r = admin.get(f"{API}/needs-grid", params={"date": date})
    assert r.status_code == 200
    rows = [x for x in r.json() if x["ics_no"] == ics and x["type"] == typ]
    assert len(rows) == 1, f"expected 1 row got {len(rows)}"
    return rows[0]


def cell(admin, field, value, ics=ICS_A, typ=TYPE_A, date=DATE):
    return admin.patch(f"{API}/needs-grid/cell", json={"date": date, "ics_no": ics, "type": typ, "field": field, "value": value})


# --- GET needs-grid
class TestNeedsGridGet:
    def test_rows_equal_master_count(self, admin):
        r = admin.get(f"{API}/needs-grid", params={"date": "2031-02-02"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == mongo.items.count_documents({})
        x = data[0]
        for k in ("id", "master_found", "lane", "product", "ics_name", "proses_mesin", "group", "std_stock_min", "std_stock_max",
                  "act_stock", "plan_customer", "plan_s3", "actual_s3", "plan_s1", "actual_s1", "plan_s2", "actual_s2",
                  "status_mesin_s3", "status_mesin_s1", "status_mesin_s2", "balance", "level_stock", "balance_s3",
                  "balance_s1", "balance_s2", "status_part"):
            assert k in x, k
        assert x["id"] == f"{x['ics_no']}|{x['type']}"
        assert "_id" not in x

    @pytest.mark.parametrize("d", ["2026-13-01", "abc", "15-01-2030"])
    def test_bad_date(self, admin, d):
        assert admin.get(f"{API}/needs-grid", params={"date": d}).status_code == 400


# --- ACT STOCK integration (SHIFT 3 only)
class TestActStock:
    def test_act_stock_is_shift3_total(self, admin, seed):
        row = grid_row(admin, ICS_A, TYPE_A)
        assert row["act_stock"] == 40  # 30+5+5, SHIFT 1/2 not added
        assert row["level_stock"] == 2.0  # 40/20
        b = grid_row(admin, ICS_B, TYPE_B)
        assert b["act_stock"] is None and b["balance"] is None and b["status_part"] is None

    def test_smt_stock_cell_updates_act_stock(self, admin, seed):
        rid = seed["stk"]["SHIFT 3"]
        r = admin.patch(f"{API}/smt-stock/{rid}/cell", json={"field": "group1", "value": 50})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 60 and d["group1"] == 50 and "indikator" in d
        assert grid_row(admin, ICS_A, TYPE_A)["act_stock"] == 60
        # restore 30 -> total 40
        assert admin.patch(f"{API}/smt-stock/{rid}/cell", json={"field": "group1", "value": "30"}).json()["total"] == 40

    @pytest.mark.parametrize("field,value", [("total", 1), ("lane", 1), ("group1", "12a"), ("group1", 1.5), ("group1", -1), ("group1", "-1")])
    def test_smt_stock_cell_validation(self, admin, seed, field, value):
        r = admin.patch(f"{API}/smt-stock/{seed['stk']['SHIFT 3']}/cell", json={"field": field, "value": value})
        assert r.status_code == 400, f"{field}={value!r} -> {r.status_code} {r.text}"

    def test_smt_stock_cell_null_and_audit(self, admin, seed):
        rid = seed["stk"]["SHIFT 3"]
        r = admin.patch(f"{API}/smt-stock/{rid}/cell", json={"field": "part_ragu", "value": ""})
        assert r.status_code == 200 and r.json()["part_ragu"] is None and r.json()["total"] == 35
        admin.patch(f"{API}/smt-stock/{rid}/cell", json={"field": "part_ragu", "value": 5})
        assert mongo.audit_log.count_documents({"module": "smt_stock", "action": "UPDATE", "record_id": rid}) >= 2 or \
            mongo.audit_log.count_documents({"module": "smt_stock", "action": "UPDATE"}) >= 2

    def test_smt_stock_cell_404(self, admin):
        assert admin.patch(f"{API}/smt-stock/000000000000000000000000/cell", json={"field": "group1", "value": 1}).status_code == 404


# --- PATCH needs-grid/cell validation + upsert
class TestNeedsCell:
    @pytest.mark.parametrize("field,value", [("plan_customer", "12a"), ("plan_customer", 1.5), ("plan_customer", -1),
                                             ("plan_customer", "-1"), ("plan_customer", "1.5"), ("status_mesin_s3", "RUN"),
                                             ("balance", 1), ("std_stock_min", 1), ("lane", "X"), ("act_stock", 1)])
    def test_invalid(self, admin, seed, field, value):
        r = cell(admin, field, value)
        assert r.status_code == 400, f"{field}={value!r} -> {r.status_code} {r.text}"

    def test_unknown_item_404(self, admin):
        assert cell(admin, "plan_customer", 1, ics="9999999999", typ="ZT NOPE").status_code == 404

    def test_upsert_no_duplicate_and_audit(self, admin, seed):
        before = mongo.audit_log.count_documents({"module": "production_needs", "action": "UPDATE"})
        for v in (5, 6, 7):
            r = cell(admin, "plan_s3", v)
            assert r.status_code == 200 and r.json()["plan_s3"] == v
        assert mongo.needs_entries.count_documents({"date": DATE, "ics_no": ICS_A, "type": TYPE_A}) == 1
        assert mongo.audit_log.count_documents({"module": "production_needs", "action": "UPDATE"}) >= before + 3
        r = cell(admin, "plan_s3", "")
        assert r.json()["plan_s3"] is None
        assert grid_row(admin, ICS_A, TYPE_A)["plan_s3"] is None

    def test_status_mesin_independent(self, admin, seed):
        assert cell(admin, "status_mesin_s3", "on").json()["status_mesin_s3"] == "ON"
        assert cell(admin, "status_mesin_s1", "DANDORI").status_code == 200
        assert cell(admin, "status_mesin_s2", "OFF").status_code == 200
        row = grid_row(admin, ICS_A, TYPE_A)
        assert (row["status_mesin_s3"], row["status_mesin_s1"], row["status_mesin_s2"]) == ("ON", "DANDORI", "OFF")
        assert cell(admin, "status_mesin_s1", None).json()["status_mesin_s1"] is None
        row = grid_row(admin, ICS_A, TYPE_A)
        assert row["status_mesin_s3"] == "ON" and row["status_mesin_s2"] == "OFF"

    def test_balance_sx(self, admin, seed):
        cell(admin, "plan_s1", 10)
        r = cell(admin, "actual_s1", 7).json()
        assert r["balance_s1"] == -3
        r = cell(admin, "plan_s1", None).json()
        assert r["balance_s1"] == 7
        r = cell(admin, "actual_s1", None).json()
        assert r["balance_s1"] is None


# --- STATUS PART acceptance (MIN 0, MAX 20 -> MID 10; act_stock 40)
class TestStatusPart:
    @pytest.mark.parametrize("plan,exp_bal,exp", [(40, 0, "SHORTAGE"), (41, -1, "SHORTAGE"), (39, 1, "POTENSI SHORTAGE"),
                                                  (30, 10, "POTENSI SHORTAGE"), (29, 11, "TIDAK SHORTAGE")])
    def test_status(self, admin, seed, plan, exp_bal, exp):
        for f in ("actual_s3", "actual_s1", "actual_s2"):
            cell(admin, f, None)
        r = cell(admin, "plan_customer", plan).json()
        assert r["balance"] == exp_bal and r["status_part"] == exp, r
        g = grid_row(admin, ICS_A, TYPE_A)
        assert g["balance"] == exp_bal and g["status_part"] == exp

    def test_balance_formula_with_actuals(self, admin, seed):
        cell(admin, "plan_customer", 50)
        cell(admin, "actual_s3", 3)
        cell(admin, "actual_s1", 4)
        r = cell(admin, "actual_s2", 5).json()
        assert r["balance"] == 40 - 50 + 12 == 2
        for f in ("actual_s3", "actual_s1", "actual_s2"):
            cell(admin, f, None)

    def test_master_change_reflects_and_not_mixed(self, admin, seed):
        cell(admin, "plan_customer", 29)  # balance 11
        item = {k: v for k, v in seed["a"].items() if k not in ("id",)}
        r = admin.put(f"{API}/items/{seed['a']['id']}", json={**item, "std_stock_min": 20, "std_stock_max": 40})  # MID 30
        assert r.status_code == 200, r.text
        g = grid_row(admin, ICS_A, TYPE_A)
        assert g["std_stock_max"] == 40 and g["status_part"] == "POTENSI SHORTAGE" and g["level_stock"] == 1.0
        b = grid_row(admin, ICS_B, TYPE_B)
        assert b["std_stock_max"] is None and b["plan_customer"] is None
        # STD BELUM DISET: remove std on item A
        r = admin.put(f"{API}/items/{seed['a']['id']}", json={**item, "std_stock_min": None, "std_stock_max": None})
        assert grid_row(admin, ICS_A, TYPE_A)["status_part"] == "STD BELUM DISET"
        admin.put(f"{API}/items/{seed['a']['id']}", json={**item, "std_stock_min": 0, "std_stock_max": 20})


# --- Permission
class TestPermission:
    def test_assy_read_ok_write_403(self, assy, seed):
        assert assy.get(f"{API}/needs-grid", params={"date": DATE}).status_code == 200
        assert cell(assy, "plan_customer", 1).status_code == 403
        assert assy.patch(f"{API}/smt-stock/{seed['stk']['SHIFT 3']}/cell", json={"field": "group1", "value": 1}).status_code == 403


# --- Regression
class TestRegression:
    @pytest.mark.parametrize("ep", ["/dashboard/summary", "/items", "/audit", "/smt-stock", "/smt-production", "/production-needs",
                                    "/variance", "/meta/options", "/backup/export"])
    def test_endpoints(self, admin, ep):
        assert admin.get(f"{API}{ep}").status_code == 200
