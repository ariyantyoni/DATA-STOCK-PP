"""Backend tests for the merged Produksi SMT & ASSY module (iteration 4)."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inventory-ops-pro-3.preview.emergentagent.com").rstrip("/")
if not BASE_URL.startswith("http"):
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"username": "admin", "password": "admin123"}
SEED_CSV = "/app/backend/seed/smt_production.csv"


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN)


# -------------------- CRUD & formulas --------------------
class TestSMTProductionCRUD:
    ICS = "9999999999"

    def _cleanup(self, tok):
        rows = requests.get(f"{API}/smt-production?ics_no={self.ICS}", headers=auth(tok), timeout=15).json()
        for r in rows:
            requests.delete(f"{API}/smt-production/{r['id']}", headers=auth(tok), timeout=10)

    def test_create_update_delete(self, admin_token):
        self._cleanup(admin_token)
        payload = {"date": "2030-01-01", "lane": "LX", "product": "REGULER", "type": "TEST",
                   "ics_no": self.ICS, "tt": 30, "planing": 1000,
                   "act_s3": 300, "act_s1": 400, "act_s2": 200,
                   "plan_assy_s3": 250, "plan_assy_s1": 250, "plan_assy_s2": 250}
        r = requests.post(f"{API}/smt-production", json=payload, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["cap_h"] == 120
        assert d["total_smt"] == 900.0
        assert d["achv"] == 90.0
        assert d["total_plan"] == 750.0
        assert d["balance"] == 150.0
        assert d["status"] == "PROSES"
        assert d["product"] == "REGULER"
        rid = d["id"]

        # GET verify persistence
        g = requests.get(f"{API}/smt-production?ics_no={self.ICS}", headers=auth(admin_token), timeout=15).json()
        assert any(x["id"] == rid for x in g)

        # PUT act_s2=300 -> total 1000 achv 100 SELESAI
        payload["act_s2"] = 300
        r = requests.put(f"{API}/smt-production/{rid}", json=payload, headers=auth(admin_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["total_smt"] == 1000.0
        assert d["achv"] == 100.0
        assert d["status"] == "SELESAI"

        # DELETE
        r = requests.delete(f"{API}/smt-production/{rid}", headers=auth(admin_token), timeout=10)
        assert r.status_code == 200
        g = requests.get(f"{API}/smt-production?ics_no={self.ICS}", headers=auth(admin_token), timeout=15).json()
        assert not any(x["id"] == rid for x in g)


# -------------------- Seed / lists / filters --------------------
class TestSMTProductionList:
    def test_seed_86(self, admin_token):
        r = requests.get(f"{API}/smt-production", headers=auth(admin_token), timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 86, f"expected >=86, got {len(rows)}"
        # sanity: rows for seed dates 2026-09-12 exist
        assert sum(1 for r in rows if r["date"] == "2026-09-12") >= 80
        assert any(r["date"] == "2026-09-15" for r in rows)
        # no ObjectId
        assert "_id" not in rows[0]
        assert "id" in rows[0]

    def test_filter_date_range(self, admin_token):
        r = requests.get(f"{API}/smt-production?date_from=2026-09-12&date_to=2026-09-12",
                         headers=auth(admin_token), timeout=15).json()
        assert all(x["date"] == "2026-09-12" for x in r)
        assert len(r) >= 80

    def test_filter_lane_and_ics(self, admin_token):
        rows = requests.get(f"{API}/smt-production", headers=auth(admin_token), timeout=15).json()
        lane = rows[0]["lane"]
        r = requests.get(f"{API}/smt-production?lane={lane}", headers=auth(admin_token), timeout=15).json()
        assert all(x["lane"] == lane for x in r)
        ics = rows[0]["ics_no"]
        r = requests.get(f"{API}/smt-production?ics_no={ics}", headers=auth(admin_token), timeout=15).json()
        assert all(x["ics_no"] == ics for x in r)

    def test_filter_status_belum_mulai(self, admin_token):
        r = requests.get(f"{API}/smt-production?status=BELUM MULAI", headers=auth(admin_token), timeout=15).json()
        assert all(x["status"] == "BELUM MULAI" for x in r)

    def test_search(self, admin_token):
        rows = requests.get(f"{API}/smt-production", headers=auth(admin_token), timeout=15).json()
        ics = rows[0]["ics_no"]
        r = requests.get(f"{API}/smt-production?search={ics}", headers=auth(admin_token), timeout=15).json()
        assert len(r) >= 1

    def test_lamp_production_removed(self, admin_token):
        r = requests.get(f"{API}/lamp-production", headers=auth(admin_token), timeout=15)
        assert r.status_code == 404, f"expected 404 for removed /lamp-production, got {r.status_code}"


# -------------------- Import CSV --------------------
class TestImport:
    def test_template_headers(self, admin_token):
        r = requests.get(f"{API}/import/smt-production/template", headers=auth(admin_token), timeout=20)
        assert r.status_code == 200
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(r.content))
        ws = wb.active
        headers = [c.value for c in ws[1]]
        expected = ["TANGGAL", "LANE", "PRODUCT", "TYPE", "ICS NO", "T/T", "PLANING",
                    "ACT S3", "ACT S1", "ACT S2", "PLAN ASSY S3", "PLAN ASSY S1", "PLAN ASSY S2"]
        assert headers == expected, f"template headers mismatch: {headers}"

    def test_preview_and_confirm_seed_csv(self, admin_token):
        with open(SEED_CSV, "rb") as f:
            content = f.read()
        # preview
        files = {"file": ("smt_production.csv", content, "text/csv")}
        r = requests.post(f"{API}/import/smt-production/preview", files=files,
                          headers=auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 86, f"preview total expected 86 got {d['total']}"
        assert d["invalid"] == 1, f"preview invalid expected 1 got {d['invalid']}"
        assert d["unknown_columns"] == [], f"expected no unknown cols, got {d['unknown_columns']}"

        # count before
        rows_before = requests.get(f"{API}/smt-production", headers=auth(admin_token), timeout=15).json()
        cnt_before = len(rows_before)

        # confirm - idempotent
        files = {"file": ("smt_production.csv", content, "text/csv")}
        r = requests.post(f"{API}/import/smt-production/confirm", files=files,
                          headers=auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["inserted"] == 0, f"inserted expected 0 got {d['inserted']}"
        assert d["updated"] == 85, f"updated expected 85 got {d['updated']}"
        assert d["skipped"] == 1, f"skipped expected 1 got {d['skipped']}"

        rows_after = requests.get(f"{API}/smt-production", headers=auth(admin_token), timeout=15).json()
        assert len(rows_after) == cnt_before, "seed count changed after idempotent import"

    def test_ics_zero_pad_on_import(self, admin_token):
        # unique test ICS
        raw_ics = "634912900"
        padded = "0634912900"
        csv = ("TANGGAL,LANE,PRODUCT,TYPE,ICS NO,T/T,PLANING,ACT S3,ACT S1,ACT S2,"
               "PLAN ASSY S3,PLAN ASSY S1,PLAN ASSY S2\n"
               f"9/20/2030,LZ,REGULER,TEST_ZPAD,{raw_ics},60,100,10,20,30,10,10,10\n")
        # cleanup first
        for ics in (raw_ics, padded):
            for r in requests.get(f"{API}/smt-production?ics_no={ics}",
                                  headers=auth(admin_token), timeout=15).json():
                requests.delete(f"{API}/smt-production/{r['id']}", headers=auth(admin_token), timeout=10)

        files = {"file": ("t.csv", csv.encode(), "text/csv")}
        r = requests.post(f"{API}/import/smt-production/confirm", files=files,
                          headers=auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["inserted"] == 1

        found = requests.get(f"{API}/smt-production?ics_no={padded}",
                             headers=auth(admin_token), timeout=15).json()
        assert len(found) == 1, f"row not saved with padded ics: {found}"
        assert found[0]["ics_no"] == padded

        # cleanup
        requests.delete(f"{API}/smt-production/{found[0]['id']}",
                        headers=auth(admin_token), timeout=10)


# -------------------- Dashboard --------------------
class TestDashboard:
    def test_summary_smt_keys(self, admin_token):
        r = requests.get(f"{API}/dashboard/summary", headers=auth(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        kpi = d["kpi"]
        for k in ("smt_total", "smt_plan", "smt_achievement", "plan_assy", "balance", "smt_items"):
            assert k in kpi, f"missing kpi key {k}"
        assert d["smt_trend"] and all(all(k in t for k in ("plan", "actual", "plan_assy")) for t in d["smt_trend"])
        assert d["smt_by_lane"]
        for row in d["smt_by_lane"]:
            for k in ("act_s3", "act_s1", "act_s2"):
                assert k in row


# -------------------- Master Item --------------------
class TestItems:
    def test_items_have_product(self, admin_token):
        r = requests.get(f"{API}/items", headers=auth(admin_token), timeout=20)
        assert r.status_code == 200
        items = r.json()
        assert items, "no items seeded"
        assert all("product" in it for it in items)
        products = {it.get("product") for it in items}
        # at least REGULER should appear (fallback)
        assert "REGULER" in products, f"products seen: {products}"
