"""Backend tests for Control Data Stock & Production."""
import os
import io
import pytest
import requests
from datetime import date

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inventory-ops-pro-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "ariyantyoni@gmail.com", "password": "admin123"}
ASSY = {"email": "assy@cds.co.id", "password": "password123"}
PPIC = {"email": "ppic@cds.co.id", "password": "password123"}
SMT = {"email": "smt@cds.co.id", "password": "password123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], data["user"]


@pytest.fixture(scope="session")
def admin_token():
    tok, _ = _login(ADMIN)
    return tok


@pytest.fixture(scope="session")
def assy_token():
    tok, _ = _login(ASSY)
    return tok


@pytest.fixture(scope="session")
def ppic_token():
    tok, _ = _login(PPIC)
    return tok


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Auth ----------
class TestAuth:
    def test_login_admin(self):
        tok, user = _login(ADMIN)
        assert user["role"] == "admin"
        assert user["email"] == ADMIN["email"]
        assert isinstance(tok, str) and len(tok) > 20

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": "no@no.co", "password": "x"}, timeout=15)
        assert r.status_code == 401

    def test_me(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_me_no_auth(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# ---------- Dashboard & Meta ----------
class TestDashboard:
    def test_summary(self, admin_token):
        r = requests.get(f"{API}/dashboard/summary", headers=auth(admin_token), timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "kpi" in d and "smt_trend" in d and "stock_status" in d and "top_shortage" in d
        assert d["kpi"]["stock_total"] >= 6

    def test_summary_date_filter(self, admin_token):
        r = requests.get(f"{API}/dashboard/summary?date_from=2099-01-01&date_to=2099-12-31",
                         headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["kpi"]["smt_target"] == 0

    def test_meta_options(self, admin_token):
        r = requests.get(f"{API}/meta/options", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["lanes", "types", "part_numbers", "shifts", "stock_status"]:
            assert k in d


# ---------- Lists ----------
class TestLists:
    @pytest.mark.parametrize("path", ["smt-production", "lamp-production", "smt-stock",
                                       "production-needs", "variance"])
    def test_list_ok(self, admin_token, path):
        r = requests.get(f"{API}/{path}", headers=auth(admin_token), timeout=20)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        if arr:
            assert "id" in arr[0]
            assert "_id" not in arr[0]

    def test_needs_enriched(self, admin_token):
        r = requests.get(f"{API}/production-needs", headers=auth(admin_token), timeout=15)
        arr = r.json()
        assert arr, "expected seeded needs data"
        n = arr[0]
        for k in ["stock_actual", "balance", "shortage_qty", "status"]:
            assert k in n
        assert n["status"] in ("SHORTAGE", "CUKUP", "PAS")


# ---------- SMT Production CRUD + auto-calc ----------
class TestSMTProduction:
    def test_crud_calc(self, admin_token):
        payload = {"date": date.today().isoformat(), "lane": "Lane 1", "shift": "Shift 1",
                   "part_number": "TEST-PN", "type": "TEST", "target": 1000,
                   "actual": 950, "defect": 50}
        r = requests.post(f"{API}/smt-production", json=payload, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["good"] == 900
        assert d["achievement"] == 95.0
        assert d["yield_rate"] == round(900/950*100, 1)
        rid = d["id"]

        # update
        up = {**payload, "actual": 1000, "defect": 20}
        r = requests.put(f"{API}/smt-production/{rid}", json=up, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d2 = r.json()
        assert d2["good"] == 980
        assert d2["achievement"] == 100.0

        # delete
        r = requests.delete(f"{API}/smt-production/{rid}", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200


# ---------- Stock auto status ----------
class TestSMTStock:
    def test_status_computed(self, admin_token):
        # critical: actual < safety
        p = {"part_number": "TEST-STK-1", "description": "t", "type": "Component",
             "unit": "Reel", "actual_stock": 10, "safety_stock": 50, "reorder_level": 100}
        r = requests.post(f"{API}/smt-stock", json=p, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "CRITICAL"
        rid = r.json()["id"]

        # reorder
        r = requests.put(f"{API}/smt-stock/{rid}",
                         json={**p, "actual_stock": 70}, headers=auth(admin_token), timeout=15)
        assert r.json()["status"] == "REORDER"

        # aman
        r = requests.put(f"{API}/smt-stock/{rid}",
                         json={**p, "actual_stock": 200}, headers=auth(admin_token), timeout=15)
        assert r.json()["status"] == "AMAN"

        requests.delete(f"{API}/smt-stock/{rid}", headers=auth(admin_token), timeout=15)


# ---------- Variance ----------
class TestVariance:
    def test_variance_calc(self, admin_token):
        p = {"date": date.today().isoformat(), "part_number": "TEST-VAR", "type": "Component",
             "system_stock": 1000, "physical_stock": 950}
        r = requests.post(f"{API}/variance", json=p, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["variance"] == -50
        assert d["variance_status"] == "SHORTAGE"
        assert d["accuracy"] == 95.0
        requests.delete(f"{API}/variance/{d['id']}", headers=auth(admin_token), timeout=15)


# ---------- LAMP status ----------
class TestLamp:
    def test_status(self, admin_token):
        p = {"date": date.today().isoformat(), "lane": "Head Lamp Line A", "type": "HL-ADV150",
             "shift": "Shift 1", "part_number": "HL-ADV150", "target": 500, "actual": 500}
        r = requests.post(f"{API}/lamp-production", json=p, headers=auth(admin_token), timeout=15)
        d = r.json()
        assert d["status"] == "SELESAI"
        assert d["achievement"] == 100.0
        requests.delete(f"{API}/lamp-production/{d['id']}", headers=auth(admin_token), timeout=15)


# ---------- Role-based access ----------
class TestRBAC:
    def test_assy_cannot_write_smt(self, assy_token):
        p = {"date": date.today().isoformat(), "lane": "Lane 1", "shift": "Shift 1",
             "part_number": "X", "type": "X", "target": 1, "actual": 1, "defect": 0}
        r = requests.post(f"{API}/smt-production", json=p, headers=auth(assy_token), timeout=15)
        assert r.status_code == 403

    def test_assy_can_write_lamp(self, assy_token):
        p = {"date": date.today().isoformat(), "lane": "Head Lamp Line A", "type": "T",
             "shift": "Shift 1", "part_number": "T", "target": 100, "actual": 50}
        r = requests.post(f"{API}/lamp-production", json=p, headers=auth(assy_token), timeout=15)
        assert r.status_code == 200
        rid = r.json()["id"]
        requests.delete(f"{API}/lamp-production/{rid}", headers=auth(assy_token), timeout=15)

    def test_ppic_cannot_write_smt_prod(self, ppic_token):
        p = {"date": date.today().isoformat(), "lane": "Lane 1", "shift": "Shift 1",
             "part_number": "X", "type": "X", "target": 1, "actual": 1, "defect": 0}
        r = requests.post(f"{API}/smt-production", json=p, headers=auth(ppic_token), timeout=15)
        assert r.status_code == 403

    def test_ppic_can_write_stock(self, ppic_token):
        p = {"part_number": "TEST-PPIC", "description": "t", "type": "Component",
             "unit": "Reel", "actual_stock": 100, "safety_stock": 50, "reorder_level": 70}
        r = requests.post(f"{API}/smt-stock", json=p, headers=auth(ppic_token), timeout=15)
        assert r.status_code == 200
        requests.delete(f"{API}/smt-stock/{r.json()['id']}", headers=auth(ppic_token), timeout=15)

    def test_non_admin_cannot_create_user(self, assy_token):
        r = requests.post(f"{API}/auth/register",
                          json={"email": "x@x.co", "password": "p", "name": "X", "role": "smt"},
                          headers=auth(assy_token), timeout=15)
        assert r.status_code == 403


# ---------- User management ----------
class TestUsers:
    def test_admin_create_delete(self, admin_token):
        email = "test_user_temp@cds.co.id"
        # cleanup pre-existing
        r = requests.get(f"{API}/users", headers=auth(admin_token), timeout=15)
        for u in r.json():
            if u["email"] == email:
                requests.delete(f"{API}/users/{u['id']}", headers=auth(admin_token), timeout=15)

        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "pass1234", "name": "TEST U", "role": "smt"},
                          headers=auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        uid = r.json()["id"]

        r = requests.delete(f"{API}/users/{uid}", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200

    def test_cannot_delete_main_admin(self, admin_token):
        r = requests.get(f"{API}/users", headers=auth(admin_token), timeout=15)
        admin_row = next(u for u in r.json() if u["email"] == ADMIN["email"])
        r = requests.delete(f"{API}/users/{admin_row['id']}", headers=auth(admin_token), timeout=15)
        assert r.status_code == 400


# ---------- Import ----------
class TestImport:
    def test_preview_and_confirm_smt_stock(self, admin_token):
        csv = "part_number,description,unit,actual_stock,safety_stock,reorder_level\nTEST-IMP-1,Imp Part,Reel,500,100,200\n"
        files = {"file": ("t.csv", io.BytesIO(csv.encode()), "text/csv")}
        r = requests.post(f"{API}/import/smt-stock/preview", files=files,
                          headers=auth(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "part_number" in d["columns"]
        assert d["total"] == 1

        files = {"file": ("t.csv", io.BytesIO(csv.encode()), "text/csv")}
        r = requests.post(f"{API}/import/smt-stock/confirm", files=files,
                          headers=auth(admin_token), timeout=20)
        assert r.status_code == 200
        assert r.json()["inserted"] == 1

        # cleanup
        r = requests.get(f"{API}/smt-stock?part_number=TEST-IMP-1",
                         headers=auth(admin_token), timeout=15)
        for row in r.json():
            requests.delete(f"{API}/smt-stock/{row['id']}", headers=auth(admin_token), timeout=15)

    def test_import_forbidden_for_wrong_role(self, assy_token):
        csv = "part_number,description,unit,actual_stock,safety_stock,reorder_level\nX,X,Reel,1,1,1\n"
        files = {"file": ("t.csv", io.BytesIO(csv.encode()), "text/csv")}
        r = requests.post(f"{API}/import/smt-stock/confirm", files=files,
                          headers=auth(assy_token), timeout=20)
        assert r.status_code == 403
