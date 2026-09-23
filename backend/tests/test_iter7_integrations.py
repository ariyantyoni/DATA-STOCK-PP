"""Iteration 7 backend regression:
- Master Item tt_assy & material_per_unit
- Stock Standards CRUD + duplicate 409
- Stock SMT indikator (PASS/MINUS/OVER/BELUM DISET) + status filter
- Production-Needs view (kondisi_produksi, stock_ok_today, waktu_shortage, blc, status)
- Variance view (prev-total, smt_total, assy_total, sistem, variance, variance_status)
- PRODUCT filter across modules + dashboard
- Permissions: smt read on views but no write on stock_standards
- Existing seed data untouched
"""
import os
import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"

ADMIN = {"username": "admin", "password": "admin123"}
SMT_USER = {"username": "smt", "password": "password123"}

ICS = "9900000001"
LANE = "ZZ9"
PROD = "REGULER"
TYPE = "UJI SPEC"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def smt_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=SMT_USER, timeout=15)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


def _delete_test_rows(admin_session):
    """Delete test rows (idempotent)."""
    for ds, q in [
        ("smt-production", {"ics_no": ICS}),
        ("smt-stock", {"ics_no": ICS}),
        ("items", {"ics_no": ICS}),
        ("stock-standards", {"product": PROD, "lane": LANE}),
    ]:
        r = admin_session.get(f"{API}/{ds}", params=q, timeout=15)
        if r.status_code == 200:
            for row in r.json():
                # ensure matches test lane/product
                if ds == "stock-standards" and (row.get("product"), row.get("lane")) != (PROD, LANE):
                    continue
                if ds != "stock-standards" and row.get("ics_no") != ICS:
                    continue
                admin_session.delete(f"{API}/{ds}/{row['id']}", timeout=15)


@pytest.fixture(scope="module", autouse=True)
def setup_teardown(admin_session):
    # baseline document counts (existing data preservation check)
    counts_before = {
        m: admin_session.get(f"{API}/{m}").json()
        for m in ("smt-production", "smt-stock", "items")
    }
    counts_before = {m: len(v) for m, v in counts_before.items()}
    _delete_test_rows(admin_session)
    yield counts_before
    _delete_test_rows(admin_session)
    # verify counts NOT smaller than before test (may be same or higher for items etc)
    counts_after = {
        m: len(admin_session.get(f"{API}/{m}").json())
        for m in ("smt-production", "smt-stock", "items")
    }
    for m in counts_before:
        assert counts_after[m] >= counts_before[m], f"{m} shrunk: {counts_before[m]} → {counts_after[m]}"


# ---------------------------------------------------------------- Setup helpers

def test_00_create_item(admin_session):
    body = {"lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS,
            "tt": 30, "tt_assy": 36, "material_per_unit": 1}
    r = admin_session.post(f"{API}/items", json=body, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["tt_assy"] == 36 and d["material_per_unit"] == 1 and d["product"] == PROD


def test_01_stock_standard_create_and_dup(admin_session):
    body = {"product": PROD, "lane": LANE, "standard_stock": 100}
    r = admin_session.post(f"{API}/stock-standards", json=body, timeout=15)
    assert r.status_code == 200, r.text
    r2 = admin_session.post(f"{API}/stock-standards", json=body, timeout=15)
    assert r2.status_code == 409
    d = r2.json()["detail"]
    assert d["code"] == "DUPLICATE"


def test_02_create_stocks(admin_session):
    for date, ok in [("2026-10-01", 100), ("2026-10-02", 80), ("2026-10-03", 120), ("2026-10-05", 600)]:
        body = {"date": date, "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS, "ok": ok}
        r = admin_session.post(f"{API}/smt-stock", json=body, timeout=15)
        assert r.status_code == 200, f"{date}: {r.text}"


def test_03_create_production(admin_session):
    body = {"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS,
            "tt": 30, "planing_smt": 500, "act_smt_s1": 90, "plan_assy": 100, "act_assy_s1": 100}
    r = admin_session.post(f"{API}/smt-production", json=body, timeout=15)
    assert r.status_code == 200, r.text


# --------------------------------------------------------------- Indikator tests

def test_10_indikator_pass_minus_over(admin_session):
    r = admin_session.get(f"{API}/smt-stock", params={"ics_no": ICS}, timeout=15)
    assert r.status_code == 200
    rows = {x["date"]: x for x in r.json()}
    assert rows["2026-10-01"]["indikator"] == "PASS"
    assert rows["2026-10-01"]["standard_stock"] == 100
    assert rows["2026-10-02"]["indikator"] == "MINUS"
    assert rows["2026-10-03"]["indikator"] == "OVER"


def test_11_indikator_filter(admin_session):
    r = admin_session.get(f"{API}/smt-stock", params={"ics_no": ICS, "status": "OVER"}, timeout=15)
    assert r.status_code == 200
    for x in r.json():
        assert x["indikator"] == "OVER"


def test_12_belum_diset_for_unmapped(admin_session):
    """Ensure records for ICS without stock-standard have BELUM DISET."""
    r = admin_session.get(f"{API}/smt-stock", timeout=15).json()
    others = [x for x in r if x["ics_no"] != ICS][:20]
    # at least one existing record should have indikator == BELUM DISET
    assert any(x["indikator"] == "BELUM DISET" for x in others), "expected some BELUM DISET"


# ------------------------------------------------------------------ Needs view

def test_20_needs_kondisi_on_shortage_hours(admin_session):
    r = admin_session.get(f"{API}/production-needs", params={"ics_no": ICS}, timeout=15)
    assert r.status_code == 200
    rows = {x["date"]: x for x in r.json()}
    row = rows["2026-10-05"]
    assert row["kondisi_produksi"] == "ON"
    assert row["stock_ok_today"] == 600
    assert row["tt_assy"] == 36
    assert row["material_per_unit"] == 1
    assert row["waktu_shortage"] == 6.0
    assert row["plan_assy"] == 100
    assert row["blc"] == 500
    assert row["status"] == "CUKUP"


def test_21_needs_off_when_zero_planning(admin_session):
    # find the production row id
    prod = admin_session.get(f"{API}/smt-production", params={"ics_no": ICS}, timeout=15).json()
    pid = [x for x in prod if x["date"] == "2026-10-05"][0]["id"]
    r = admin_session.put(f"{API}/smt-production/{pid}",
                          json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS,
                                "tt": 30, "planing_smt": 0, "plan_assy": 0, "act_smt_s1": 90, "act_assy_s1": 100},
                          timeout=15)
    assert r.status_code == 200
    n = admin_session.get(f"{API}/production-needs", params={"ics_no": ICS}, timeout=15).json()
    row = [x for x in n if x["date"] == "2026-10-05"][0]
    assert row["kondisi_produksi"] == "OFF"
    assert row["waktu_shortage"] is None
    # restore
    admin_session.put(f"{API}/smt-production/{pid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS,
                            "tt": 30, "planing_smt": 500, "plan_assy": 100, "act_smt_s1": 90, "act_assy_s1": 100},
                      timeout=15)


def test_22_needs_scales_with_stock_and_tt(admin_session):
    st = admin_session.get(f"{API}/smt-stock", params={"ics_no": ICS}, timeout=15).json()
    sid = [x for x in st if x["date"] == "2026-10-05"][0]["id"]
    # stock 300 → 3.0 jam
    admin_session.put(f"{API}/smt-stock/{sid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS, "ok": 300},
                      timeout=15)
    row = [x for x in admin_session.get(f"{API}/production-needs", params={"ics_no": ICS}).json() if x["date"] == "2026-10-05"][0]
    assert row["waktu_shortage"] == 3.0, row
    # tt_assy 72 → 6.0 jam
    it = admin_session.get(f"{API}/items", params={"ics_no": ICS}, timeout=15).json()[0]
    admin_session.put(f"{API}/items/{it['id']}",
                      json={**it, "tt_assy": 72}, timeout=15)
    row = [x for x in admin_session.get(f"{API}/production-needs", params={"ics_no": ICS}).json() if x["date"] == "2026-10-05"][0]
    assert row["waktu_shortage"] == 6.0
    # restore
    admin_session.put(f"{API}/smt-stock/{sid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS, "ok": 600},
                      timeout=15)
    admin_session.put(f"{API}/items/{it['id']}",
                      json={**it, "tt_assy": 36}, timeout=15)
    row = [x for x in admin_session.get(f"{API}/production-needs", params={"ics_no": ICS}).json() if x["date"] == "2026-10-05"][0]
    assert row["waktu_shortage"] == 6.0


# --------------------------------------------------------------- Variance view

def test_30_variance_all_scenarios(admin_session):
    v = admin_session.get(f"{API}/variance", params={"ics_no": ICS}, timeout=15).json()
    rows = {x["date"]: x for x in v}
    assert rows["2026-10-01"]["variance_status"] == "BELUM DICEK"
    assert rows["2026-10-01"]["total_stock_prev"] is None
    r2 = rows["2026-10-02"]
    assert r2["total_stock_prev"] == 100 and r2["stock_sistem"] == 100 and r2["actual_total_stock"] == 80
    assert r2["variance"] == -20 and r2["variance_status"] == "VARIANCE -"
    r3 = rows["2026-10-03"]
    assert r3["stock_sistem"] == 80 and r3["variance"] == 40 and r3["variance_status"] == "VARIANCE +"
    r5 = rows["2026-10-05"]
    assert r5["total_stock_prev"] == 120
    assert r5["smt_total"] == 90 and r5["assy_total"] == 100
    assert r5["stock_sistem"] == 110 and r5["actual_total_stock"] == 600
    assert r5["variance"] == 490


def test_31_variance_updates_with_production(admin_session):
    prod = admin_session.get(f"{API}/smt-production", params={"ics_no": ICS}, timeout=15).json()
    pid = [x for x in prod if x["date"] == "2026-10-05"][0]["id"]
    admin_session.put(f"{API}/smt-production/{pid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS,
                            "tt": 30, "planing_smt": 500, "plan_assy": 100, "act_smt_s1": 190, "act_assy_s1": 100},
                      timeout=15)
    r = [x for x in admin_session.get(f"{API}/variance", params={"ics_no": ICS}).json() if x["date"] == "2026-10-05"][0]
    assert r["smt_total"] == 190 and r["stock_sistem"] == 210
    admin_session.put(f"{API}/smt-production/{pid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS,
                            "tt": 30, "planing_smt": 500, "plan_assy": 100, "act_smt_s1": 190, "act_assy_s1": 300},
                      timeout=15)
    r = [x for x in admin_session.get(f"{API}/variance", params={"ics_no": ICS}).json() if x["date"] == "2026-10-05"][0]
    assert r["assy_total"] == 300 and r["stock_sistem"] == 10


def test_32_variance_ok_case(admin_session):
    """set stock to match sistem (10) → status OK, variance 0"""
    st = admin_session.get(f"{API}/smt-stock", params={"ics_no": ICS}, timeout=15).json()
    sid = [x for x in st if x["date"] == "2026-10-05"][0]["id"]
    admin_session.put(f"{API}/smt-stock/{sid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS, "ok": 10},
                      timeout=15)
    r = [x for x in admin_session.get(f"{API}/variance", params={"ics_no": ICS}).json() if x["date"] == "2026-10-05"][0]
    assert r["variance"] == 0 and r["variance_status"] == "OK"
    # restore stock 600 & production act_smt_s1 90, act_assy_s1 100 for later tests
    admin_session.put(f"{API}/smt-stock/{sid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS, "ok": 600},
                      timeout=15)
    prod = admin_session.get(f"{API}/smt-production", params={"ics_no": ICS}, timeout=15).json()
    pid = [x for x in prod if x["date"] == "2026-10-05"][0]["id"]
    admin_session.put(f"{API}/smt-production/{pid}",
                      json={"date": "2026-10-05", "lane": LANE, "product": PROD, "type": TYPE, "ics_no": ICS,
                            "tt": 30, "planing_smt": 500, "plan_assy": 100, "act_smt_s1": 90, "act_assy_s1": 100},
                      timeout=15)


# ------------------------------------------------------------- Product filter

def test_40_product_filter_across_modules(admin_session):
    for ds in ("smt-production", "smt-stock", "production-needs", "variance"):
        r = admin_session.get(f"{API}/{ds}", params={"product": "SPO"}, timeout=15)
        assert r.status_code == 200
        for x in r.json():
            assert x.get("product") == "SPO", f"{ds} returned non-SPO: {x}"


def test_41_meta_options_products(admin_session):
    o = admin_session.get(f"{API}/meta/options", timeout=15).json()
    assert "REGULER" in o["products"]
    assert "SPO" in o["products"]


def test_42_dashboard_product_filter(admin_session):
    a = admin_session.get(f"{API}/dashboard/summary", timeout=15).json()
    b = admin_session.get(f"{API}/dashboard/summary", params={"product": "SPO"}, timeout=15).json()
    assert b["kpi"]["smt_items"] <= a["kpi"]["smt_items"]


# ---------------------------------------------------------------- Permissions

def test_50_smt_read_needs_and_variance(smt_session):
    for ds in ("production-needs", "variance"):
        r = smt_session.get(f"{API}/{ds}", timeout=15)
        assert r.status_code == 200, f"{ds}: {r.status_code}"


def test_51_smt_cannot_write_stock_standards(smt_session):
    r = smt_session.post(f"{API}/stock-standards",
                         json={"product": "REGULER", "lane": "TEST", "standard_stock": 1}, timeout=15)
    assert r.status_code == 403
