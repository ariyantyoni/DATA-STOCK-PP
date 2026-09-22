"""Iteration 6 tests: SMT Production new schema, Stock SMT prev linking, Backup & Restore."""
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inventory-ops-pro-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def smt_token():
    r = requests.post(f"{API}/auth/login", json={"username": "smt", "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


# ---------------- SMT Production new schema ----------------
class TestSMTProduction:
    def test_create_compute_update_delete(self, admin):
        payload = {"date": "2026-09-23", "lane": "R06", "product": "REGULER", "type": "UJI SMT",
                   "ics_no": "8888888888", "tt": 30, "planing_smt": 1000,
                   "act_smt_s3": 300, "act_smt_s1": 400, "act_smt_s2": 200,
                   "plan_assy": 800, "act_assy_s3": 250, "act_assy_s1": 250, "act_assy_s2": 200}
        # cleanup if exists
        existing = admin.get(f"{API}/smt-production", params={"date_from": "2026-09-23", "date_to": "2026-09-23", "ics_no": "8888888888"}).json()
        for d in existing:
            admin.delete(f"{API}/smt-production/{d['id']}")

        r = admin.post(f"{API}/smt-production", data=None, json=payload)
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert d["cap_h"] == 120
        assert d["total_act_smt"] == 900
        assert d["achv"] == 90.0
        assert d["total_act_assy"] == 700
        assert d["balance"] == 200
        assert d["status"] == "PROSES"
        rec_id = d["id"]

        # PUT update act_smt_s2 to 300
        upd = {**payload, "act_smt_s2": 300}
        r = admin.put(f"{API}/smt-production/{rec_id}", json=upd)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_act_smt"] == 1000
        assert d["achv"] == 100.0
        assert d["balance"] == 300
        assert d["status"] == "SELESAI"

        # DELETE
        r = admin.delete(f"{API}/smt-production/{rec_id}")
        assert r.status_code in (200, 204)

    def test_seed_84_rows(self, admin):
        rows = admin.get(f"{API}/smt-production", params={"date_from": "2026-09-22", "date_to": "2026-09-22"}).json()
        assert len(rows) == 84
        sample = rows[0]
        for k in ("planing_smt", "plan_assy", "act_smt_s3", "act_smt_s1", "act_smt_s2",
                  "act_assy_s3", "act_assy_s1", "act_assy_s2", "cap_h",
                  "total_act_smt", "achv", "total_act_assy", "balance", "status"):
            assert k in sample, f"missing field {k}"

    def test_template_headers(self, admin):
        # The endpoint returns xlsx; check filename and mime — content headers per FIELDS labels
        r = admin.get(f"{API}/import/smt-production/template")
        assert r.status_code == 200
        # Parse xlsx to verify header row
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(r.content))
        headers = [c.value for c in wb.active[1]]
        expected = ["TANGGAL", "LANE", "PRODUCT", "TYPE", "ICS NO", "T/T",
                    "PLANING SMT", "ACT SMT S3", "ACT SMT S1", "ACT SMT S2",
                    "PLAN ASSY", "ACT ASSY S3", "ACT ASSY S1", "ACT ASSY S2"]
        assert headers == expected, headers

    def test_import_preview_confirm_seed_all_duplicate(self, admin):
        path = "/app/backend/seed/smt_production.csv"
        with open(path, "rb") as f:
            files = {"file": ("smt_production.csv", f, "text/csv")}
            # Preview requires no Content-Type: application/json
            hdrs = {k: v for k, v in admin.headers.items() if k.lower() != "content-type"}
            r = requests.post(f"{API}/import/smt-production/preview", headers=hdrs, files=files)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["duplicates"] == 84, p
        assert p["total"] == 84

        before = len(admin.get(f"{API}/smt-production", params={"date_from": "2026-09-22", "date_to": "2026-09-22"}).json())
        with open(path, "rb") as f:
            files = {"file": ("smt_production.csv", f, "text/csv")}
            hdrs = {k: v for k, v in admin.headers.items() if k.lower() != "content-type"}
            r = requests.post(f"{API}/import/smt-production/confirm", headers=hdrs, files=files)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c.get("inserted") == 0 and c.get("updated") == 84, c
        after = len(admin.get(f"{API}/smt-production", params={"date_from": "2026-09-22", "date_to": "2026-09-22"}).json())
        assert before == after == 84

    def test_dashboard_summary_keys(self, admin):
        r = admin.get(f"{API}/dashboard/summary")
        assert r.status_code == 200
        d = r.json()
        kpi = d["kpi"]
        for k in ("smt_total", "smt_plan", "plan_assy", "assy_total", "balance"):
            assert k in kpi
        assert d["smt_trend"]
        t = d["smt_trend"][0]
        for k in ("plan", "actual", "plan_assy", "actual_assy"):
            assert k in t
        lane = d["smt_by_lane"][0]
        for k in ("act_smt_s3", "act_smt_s1", "act_smt_s2"):
            assert k in lane


# ---------------- Stock SMT prev linking ----------------
class TestStockPrevLinking:
    ICS = "5298375400"
    TYPE = "RC K3VA"

    def _cleanup(self, admin, dates):
        for date in dates:
            rows = admin.get(f"{API}/smt-stock", params={"ics_no": self.ICS, "date_from": date, "date_to": date}).json()
            for d in rows:
                if d.get("date") == date:
                    admin.delete(f"{API}/smt-stock/{d['id']}")

    def test_prev_chain(self, admin):
        self._cleanup(admin, ["2026-09-14", "2026-09-15", "2026-09-17"])

        # 2026-09-14 -> should auto-link to 2026-09-13 with OK=714
        r = admin.post(f"{API}/smt-stock", json={"date": "2026-09-14", "lane": "R06", "type": self.TYPE,
                                                 "ics_no": self.ICS, "ok": 100, "coating": 5})
        assert r.status_code in (200, 201), r.text

        rows = admin.get(f"{API}/smt-stock", params={"ics_no": self.ICS, "date_from": "2026-09-14", "date_to": "2026-09-14"}).json()
        row14 = next(x for x in rows if x["date"] == "2026-09-14")
        assert row14["stock_ok_prev"] == 714, row14
        assert row14["stock_ok_prev_source"] == "2026-09-13"

        # 2026-09-15 -> prev = 2026-09-14 OK=100
        r = admin.post(f"{API}/smt-stock", json={"date": "2026-09-15", "lane": "R06", "type": self.TYPE,
                                                 "ics_no": self.ICS, "ok": 200, "coating": 0})
        assert r.status_code in (200, 201)
        rows = admin.get(f"{API}/smt-stock", params={"ics_no": self.ICS, "date_from": "2026-09-15", "date_to": "2026-09-15"}).json()
        row15 = next(x for x in rows if x["date"] == "2026-09-15")
        assert row15["stock_ok_prev"] == 100
        assert row15["stock_ok_prev_source"] == "2026-09-14"
        rec15 = row15["id"]

        # 2026-09-17 (no 09-16 record) -> fallback to 2026-09-15
        r = admin.post(f"{API}/smt-stock", json={"date": "2026-09-17", "lane": "R06", "type": self.TYPE,
                                                 "ics_no": self.ICS, "ok": 300, "coating": 0})
        assert r.status_code in (200, 201)
        rows = admin.get(f"{API}/smt-stock", params={"ics_no": self.ICS, "date_from": "2026-09-17", "date_to": "2026-09-17"}).json()
        row17 = next(x for x in rows if x["date"] == "2026-09-17")
        assert row17["stock_ok_prev_source"] == "2026-09-15"
        assert row17["stock_ok_prev"] == 200

        # PUT 2026-09-15 with manual override
        r = admin.put(f"{API}/smt-stock/{rec15}", json={"date": "2026-09-15", "lane": "R06", "type": self.TYPE,
                                                        "ics_no": self.ICS, "ok": 200, "coating": 0,
                                                        "stock_ok_prev": 55, "stock_ok_manual": True})
        assert r.status_code == 200, r.text
        rows = admin.get(f"{API}/smt-stock", params={"ics_no": self.ICS, "date_from": "2026-09-15", "date_to": "2026-09-15"}).json()
        row15b = next(x for x in rows if x["date"] == "2026-09-15")
        assert row15b["stock_ok_prev"] == 55
        assert row15b.get("stock_ok_manual") is True

        # /api/prev-values
        r = admin.get(f"{API}/prev-values", params={"date": "2026-09-14", "ics_no": self.ICS, "type": self.TYPE})
        assert r.status_code == 200
        pv = r.json()
        assert pv["found"] is True
        assert pv["source_date"] == "2026-09-13"
        assert pv["stock_ok_prev"] == 714

        # cleanup
        self._cleanup(admin, ["2026-09-14", "2026-09-15", "2026-09-17"])


# ---------------- Backup & Restore ----------------
class TestBackupRestore:
    def test_export_preview_restore(self, admin, smt_token):
        # export
        r = admin.get(f"{API}/backup/export")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/zip")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(zf.namelist())
        expected = {"smt_production.json", "smt_stock.json", "production_needs.json",
                    "variance.json", "items.json", "users.json", "audit_log.json",
                    "notifications.json", "meta.json"}
        assert expected.issubset(names), names
        assert len(names) == 9, names
        zip_bytes = r.content

        # counts before
        counts_before = {}
        for c in ("smt-production", "smt-stock", "production-needs", "variance", "items"):
            counts_before[c] = len(admin.get(f"{API}/{c}").json())

        # preview
        hdrs = {k: v for k, v in admin.headers.items() if k.lower() != "content-type"}
        r = requests.post(f"{API}/backup/preview", headers=hdrs,
                          files={"file": ("backup.zip", zip_bytes, "application/zip")})
        assert r.status_code == 200, r.text
        pv = r.json()
        assert len(pv["modules"]) == 5
        for m in pv["modules"]:
            assert m["in_backup"] == m["current"], m

        # preview with .csv -> 400
        r = requests.post(f"{API}/backup/preview", headers=hdrs,
                          files={"file": ("x.csv", b"a,b\n1,2", "text/csv")})
        assert r.status_code == 400
        assert ".zip" in r.json().get("detail", "")

        # restore
        r = requests.post(f"{API}/backup/restore", headers=hdrs,
                          files={"file": ("backup.zip", zip_bytes, "application/zip")})
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["ok"] is True
        for c, v in res["result"].items():
            assert v["removed"] == v["restored"], (c, v)

        # counts unchanged
        for c in ("smt-production", "smt-stock", "production-needs", "variance", "items"):
            after = len(admin.get(f"{API}/{c}").json())
            assert after == counts_before[c], (c, after, counts_before[c])

        # audit contains RESTORE for 5 modules
        r = admin.get(f"{API}/audit", params={"action": "RESTORE"})
        assert r.status_code == 200
        logs = r.json()
        # logs may be array or {items:[]}
        items = logs.get("items", logs) if isinstance(logs, dict) else logs
        modules_seen = {x.get("module") for x in items[:20]}
        for m in ("smt_production", "smt_stock", "production_needs", "variance", "items"):
            assert m in modules_seen, modules_seen

        # 403 for smt user
        r = requests.get(f"{API}/backup/export", headers={"Authorization": f"Bearer {smt_token}"})
        assert r.status_code == 403
