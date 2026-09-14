"""Backend tests for Control Data Stock & Production (new Excel schema)."""
import os
import io
import time
import pytest
import requests
from openpyxl import Workbook

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://inventory-ops-pro-3.preview.emergentagent.com"
# fallback via frontend/.env if env not present
if "REACT_APP_BACKEND_URL" not in os.environ:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
API = f"{BASE_URL}/api"

ADMIN = {"email": "ariyantyoni@gmail.com", "password": "admin123"}
ASSY = {"email": "assy@cds.co.id", "password": "password123"}
PPIC = {"email": "ppic@cds.co.id", "password": "password123"}
SMT = {"email": "smt@cds.co.id", "password": "password123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    d = r.json()
    return d["token"], d["user"]


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def admin_token():
    tok, _ = _login(ADMIN)
    return tok


@pytest.fixture(scope="session")
def admin_user():
    _, u = _login(ADMIN)
    return u


@pytest.fixture(scope="session")
def assy_token():
    tok, _ = _login(ASSY)
    return tok


@pytest.fixture(scope="session")
def ppic_token():
    tok, _ = _login(PPIC)
    return tok


@pytest.fixture(scope="session")
def smt_token():
    tok, _ = _login(SMT)
    return tok


# -------------------- Auth --------------------
class TestAuth:
    def test_login_admin(self, admin_user):
        assert admin_user["role"] == "admin"
        assert admin_user["email"] == ADMIN["email"]
        assert admin_user["is_main_admin"] is True
        ep = admin_user["effective_permissions"]
        for m in ["smt_production", "lamp_production", "smt_stock", "production_needs", "variance", "users"]:
            assert ep.get(m) == "write", f"admin missing write on {m}: {ep}"

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": "no@no.co", "password": "x"}, timeout=15)
        assert r.status_code == 401

    def test_me(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "admin"
        assert "effective_permissions" in d

    def test_me_no_auth(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# -------------------- Dashboard --------------------
class TestDashboard:
    def test_summary(self, admin_token):
        r = requests.get(f"{API}/dashboard/summary", headers=auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("kpi", "stock_breakdown", "assy_trend", "smt_by_lane", "top_shortage", "top_variance"):
            assert k in d, f"missing key {k}"
        assert d["kpi"]["smt_items"] >= 1

    def test_meta_options(self, admin_token):
        r = requests.get(f"{API}/meta/options", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("lanes", "types", "ics_nos", "stock_status", "variance_status"):
            assert k in d


# -------------------- Seed / lists --------------------
class TestLists:
    @pytest.mark.parametrize("path,expected_date", [
        ("smt-production", "2026-09-12"),
        ("lamp-production", "2026-09-12"),
        ("smt-stock", "2026-09-13"),
        ("production-needs", "2026-09-12"),
        ("variance", "2026-09-13"),
    ])
    def test_seed_list(self, admin_token, path, expected_date):
        r = requests.get(f"{API}/{path}", headers=auth(admin_token), timeout=30)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        assert len(arr) >= 100, f"expected ~141 rows in {path}, got {len(arr)}"
        # seed date rows should be present (test may run alongside formula tests inserting other dates)
        assert any(x["date"] == expected_date for x in arr), f"seed date {expected_date} missing in {path}"
        assert "id" in arr[0] and "_id" not in arr[0]

    def test_filter_ics_no(self, admin_token):
        r = requests.get(f"{API}/smt-production", headers=auth(admin_token), timeout=15).json()
        ics = r[0]["ics_no"]
        r2 = requests.get(f"{API}/smt-production?ics_no={ics}", headers=auth(admin_token), timeout=15)
        assert r2.status_code == 200
        assert all(x["ics_no"] == ics for x in r2.json())


# -------------------- CRUD & formulas --------------------
class TestFormulas:
    def _cleanup(self, tok, path, rid):
        try:
            requests.delete(f"{API}/{path}/{rid}", headers=auth(tok), timeout=10)
        except Exception:
            pass

    def test_smt_production_formula(self, admin_token):
        p = {"date": "2030-01-01", "lane": "LX", "type": "TEST_TYPE", "ics_no": "TEST_SMT_01",
             "tt": 30, "led_rank": "A", "smt1": 100, "smt2": 200, "smt3": 300}
        r = requests.post(f"{API}/smt-production", json=p, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["cap_h"] == 120.0
        assert d["total"] == 600.0
        # update
        r2 = requests.put(f"{API}/smt-production/{d['id']}", json={**p, "smt3": 500}, headers=auth(admin_token))
        assert r2.status_code == 200
        assert r2.json()["total"] == 800.0
        self._cleanup(admin_token, "smt-production", d["id"])

    def test_variance_formula(self, admin_token):
        p = {"date": "2030-01-02", "lane": "LX", "type": "TEST", "ics_no": "TEST_VAR_01",
             "total_stock_prev": 1000, "smt_total": 500, "assy_total": 300, "smt3": 100,
             "assy3": 50, "actual_total_stock": 1250}
        r = requests.post(f"{API}/variance", json=p, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["stock_sistem"] == 1200.0
        assert d["variance"] == 50.0
        assert d["stok_jam"] == 1200.0
        assert d["variance_status"] == "SURPLUS"
        self._cleanup(admin_token, "variance", d["id"])

    def test_lamp_formula(self, admin_token):
        p = {"date": "2030-01-03", "lane": "LX", "type": "TEST", "ics_no": "TEST_LAMP_01",
             "plan_assy": 100, "assy1": 40, "assy2": 40, "assy3": 30, "stock_ok_prev": 200}
        r = requests.post(f"{API}/lamp-production", json=p, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 110.0
        assert d["blc"] == 100.0
        assert d["achievement"] == 110.0
        assert d["status"] == "SELESAI"
        self._cleanup(admin_token, "lamp-production", d["id"])

    def test_smt_stock_formula(self, admin_token):
        p = {"date": "2030-01-04", "lane": "LX", "type": "TEST", "ics_no": "TEST_STK_01",
             "stock_ok_prev": 0, "coating": 10, "belum_cutting": 20, "belum_ict": 30,
             "belum_fct": 40, "ok": 100, "tray": "T1"}
        r = requests.post(f"{API}/smt-stock", json=p, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 200.0
        assert d["status"] == "OK"
        self._cleanup(admin_token, "smt-stock", d["id"])

    def test_needs_formula(self, admin_token):
        p = {"date": "2030-01-05", "lane": "LX", "type": "TEST", "ics_no": "TEST_NEEDS_01",
             "plan_assy": 100, "stock_ok_prev": 80}
        r = requests.post(f"{API}/production-needs", json=p, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["blc"] == -20.0
        assert d["status"] == "SHORTAGE"
        self._cleanup(admin_token, "production-needs", d["id"])


# -------------------- Users mgmt --------------------
class TestUsers:
    def _delete_user_by_email(self, tok, email):
        r = requests.get(f"{API}/users", headers=auth(tok), timeout=15)
        for u in r.json():
            if u["email"] == email:
                requests.delete(f"{API}/users/{u['id']}", headers=auth(tok), timeout=10)

    def test_full_user_lifecycle(self, admin_token):
        email = "test_perm_user@cds.co.id"
        self._delete_user_by_email(admin_token, email)
        # create with override
        body = {"email": email, "password": "pass1234", "name": "Test Perm",
                "role": "assembly",
                "permissions": {"variance": "none", "smt_production": "write"}}
        r = requests.post(f"{API}/users", json=body, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        u = r.json()
        uid = u["id"]
        assert u["role"] == "assembly"
        assert u["effective_permissions"]["variance"] == "none"
        assert u["effective_permissions"]["smt_production"] == "write"
        # login as new user
        tok, me = _login({"email": email, "password": "pass1234"})
        # GET variance -> 403
        r = requests.get(f"{API}/variance", headers=auth(tok), timeout=15)
        assert r.status_code == 403
        # POST smt-production -> 200
        p = {"date": "2030-02-01", "lane": "LX", "type": "T", "ics_no": "TEST_PERM_SMT",
             "tt": 60, "led_rank": "A", "smt1": 1, "smt2": 1, "smt3": 1}
        r = requests.post(f"{API}/smt-production", json=p, headers=auth(tok), timeout=15)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        requests.delete(f"{API}/smt-production/{rid}", headers=auth(admin_token))
        # POST smt-stock -> 403 (assembly default read)
        p2 = {"date": "2030-02-01", "lane": "LX", "type": "T", "ics_no": "TEST_PERM_STK",
              "coating": 0, "belum_cutting": 0, "belum_ict": 0, "belum_fct": 0, "ok": 10, "tray": "T"}
        r = requests.post(f"{API}/smt-stock", json=p2, headers=auth(tok), timeout=15)
        assert r.status_code == 403

        # PUT update
        r = requests.put(f"{API}/users/{uid}",
                         json={"name": "Updated Name", "role": "smt", "password": "newpass1",
                               "permissions": {"variance": "read"}},
                         headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        u2 = r.json()
        assert u2["name"] == "Updated Name"
        assert u2["role"] == "smt"
        assert u2["effective_permissions"]["variance"] == "read"
        # login with new password
        tok2, _ = _login({"email": email, "password": "newpass1"})
        assert tok2

        # DELETE
        r = requests.delete(f"{API}/users/{uid}", headers=auth(admin_token), timeout=15)
        assert r.status_code == 200

    def test_cannot_delete_main_admin(self, admin_token):
        r = requests.get(f"{API}/users", headers=auth(admin_token), timeout=15)
        admin_row = next(u for u in r.json() if u["email"] == ADMIN["email"])
        r = requests.delete(f"{API}/users/{admin_row['id']}", headers=auth(admin_token), timeout=15)
        assert r.status_code == 400

    def test_cannot_delete_self(self, admin_token, admin_user):
        # main admin protection triggers first (400), so create secondary admin
        email = "test_selfdel_admin@cds.co.id"
        # cleanup
        r = requests.get(f"{API}/users", headers=auth(admin_token), timeout=15)
        for u in r.json():
            if u["email"] == email:
                requests.delete(f"{API}/users/{u['id']}", headers=auth(admin_token), timeout=10)
        r = requests.post(f"{API}/users",
                          json={"email": email, "password": "pass1234", "name": "T",
                                "role": "admin", "permissions": {}},
                          headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        uid = r.json()["id"]
        tok2, _ = _login({"email": email, "password": "pass1234"})
        r = requests.delete(f"{API}/users/{uid}", headers=auth(tok2), timeout=15)
        assert r.status_code == 400
        assert "sendiri" in r.text.lower() or "self" in r.text.lower()
        # cleanup via main admin
        requests.delete(f"{API}/users/{uid}", headers=auth(admin_token), timeout=10)

    def test_non_admin_forbidden(self, assy_token):
        r = requests.get(f"{API}/users", headers=auth(assy_token), timeout=15)
        assert r.status_code == 403


# -------------------- Import + Template --------------------
class TestImport:
    def test_template_download(self, admin_token):
        r = requests.get(f"{API}/import/smt-production/template", headers=auth(admin_token), timeout=20)
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "")
        assert len(r.content) > 200

    def test_preview_and_confirm_and_reconfirm(self, admin_token):
        # Build xlsx with label headers matching template
        wb = Workbook()
        ws = wb.active
        ws.append(["Tanggal", "Lane", "Type", "ICS No.", "T/T (detik)", "LED Rank",
                   "SMT Shift 1", "SMT Shift 2", "SMT Shift 3"])
        ws.append(["2030-03-01", "LX", "IMP_TYPE", "TEST_IMP_1", 30, "A", 100, 200, 300])
        ws.append(["2030-03-01", "LX", "IMP_TYPE", "TEST_IMP_2", 60, "B", 10, 20, 30])
        buf = io.BytesIO(); wb.save(buf); buf.seek(0)
        files = {"file": ("t.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/import/smt-production/preview", files=files,
                          headers=auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 2
        assert d["rows"][0]["total"] == 600.0

        # Confirm
        buf.seek(0)
        files = {"file": ("t.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/import/smt-production/confirm", files=files,
                          headers=auth(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["inserted"] == 2
        assert d["updated"] == 0

        # Re-confirm same file -> update, insert 0
        buf.seek(0)
        files = {"file": ("t.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/import/smt-production/confirm", files=files,
                          headers=auth(admin_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["inserted"] == 0
        assert d["updated"] == 2

        # cleanup
        for ics in ("TEST_IMP_1", "TEST_IMP_2"):
            rows = requests.get(f"{API}/smt-production?ics_no={ics}", headers=auth(admin_token), timeout=15).json()
            for row in rows:
                requests.delete(f"{API}/smt-production/{row['id']}", headers=auth(admin_token), timeout=10)
