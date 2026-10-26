# Iteration 9: Master Item import robustness, needs-grid ACTUAL CUSTOMER / ACHIEVEMENT, needs import, smt-stock STATUS PART, dashboard
import io
import os
import pytest
import requests
import pandas as pd
from openpyxl import Workbook, load_workbook
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "part_production")]
PROD = "ZTPROD9"
D1, D2, D_IMP = "2031-03-01", "2031-03-02", "2031-04-01"
ICS = {k: f"99000009{n:02d}" for n, k in enumerate(["A1", "A1b", "B", "C", "D", "E", "F", "G", "H", "M1", "M2"], 1)}
TYP = {"A1": "ZT9 A98", "A1b": "ZT9 A98", "B": "ZT9 B965", "C": "ZT9 C97", "D": "ZT9 D96", "E": "ZT9 E90",
       "F": "ZT9 F95", "G": "ZT9 G8999", "H": "ZT9 H0", "M1": "ZT9 M1", "M2": "ZT9 M2"}
GRP = {"A1": "GROUP 1", "A1b": "GROUP 1", "F": "GROUP 1", "G": "GROUP 1", "B": "GROUP 2", "C": "GROUP 2", "H": "GROUP 2",
       "D": "GROUP 3", "E": "GROUP 3", "M1": "GROUP 4", "M2": "GROUP 4"}
ALL_ICS = list(ICS.values())


def login(u, p):
    r = requests.post(f"{API}/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s = requests.Session()
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    s.cookies.update(r.cookies)
    return s


def cleanup():
    for c in ("smt_stock", "needs_entries", "items"):
        mongo[c].delete_many({"ics_no": {"$in": ALL_ICS}})


@pytest.fixture(scope="module")
def admin():
    return login("admin", "admin123")


@pytest.fixture(scope="module")
def assy():
    return login("assy", "password123")


@pytest.fixture(scope="module", autouse=True)
def seed(admin):
    cleanup()
    base_count = mongo.items.count_documents({})
    for k, ics in ICS.items():
        r = admin.post(f"{API}/items", json={"lane": "ZT9", "product": PROD, "type": TYP[k], "ics_no": ics, "ics_name": f"ZT NAME {k}",
                                            "group": GRP[k], "std_stock_min": 100, "std_stock_max": 300, "tt": 36, "proses_mesin": "INJECTION"})
        assert r.status_code == 200, r.text
    stocks = [(D2, "SHIFT 3", "A1", 500), (D2, "SHIFT 3", "A1b", 10), (D2, "SHIFT 3", "B", 100), (D2, "SHIFT 3", "C", 100),
              (D2, "SHIFT 3", "D", 500), (D2, "SHIFT 1", "D", 777), (D2, "SHIFT 3", "E", 0), (D1, "SHIFT 3", "F", 0),
              (D2, "SHIFT 3", "F", 1000), (D2, "SHIFT 3", "G", 0), (D2, "SHIFT 3", "H", 50), ("2031-03-05", "SHIFT 1", "A1", 5)]
    for d, sh, k, tot in stocks:
        r = admin.post(f"{API}/smt-stock", json={"date": d, "shift": sh, "lane": "ZT9", "product": PROD, "type": TYP[k], "ics_no": ICS[k], "group1": tot})
        assert r.status_code == 200, r.text
    needs = [
        (D2, "A1", dict(plan_customer=1000, actual_customer=950, plan_s3=1000, actual_s3=980)),
        (D2, "A1b", dict(plan_customer=2000)),
        (D2, "B", dict(plan_customer=900, plan_s3=1000, actual_s3=965)),
        (D2, "C", dict(plan_customer=1000, plan_s3=1000, actual_s3=970)),
        (D2, "D", dict(plan_customer=100, plan_s3=1000, actual_s3=960)),
        (D2, "E", dict(plan_customer=1000, plan_s3=1000, actual_s3=900)),
        (D1, "F", dict(plan_customer=600, actual_customer=500, plan_s1=500, actual_s1=480)),
        (D2, "F", dict(plan_customer=100, plan_s2=500, actual_s2=470)),
        (D2, "G", dict(plan_customer=9000, plan_s3=10000, actual_s3=8999)),
        (D2, "H", dict(plan_customer=0, plan_s3=0, actual_s3=100)),
    ]
    for d, k, v in needs:
        mongo.needs_entries.insert_one({"date": d, "ics_no": ICS[k], "type": TYP[k], **v})
    yield base_count
    cleanup()
    assert mongo.items.count_documents({}) == base_count


def grow(admin, date, k):
    rows = [x for x in admin.get(f"{API}/needs-grid", params={"date": date}).json() if x["ics_no"] == ICS[k] and x["type"] == TYP[k]]
    assert len(rows) == 1
    return rows[0]


def upload(s, url, name, content, data=None):
    return s.post(url, files={"file": (name, content)}, data=data or {})


def xlsx_bytes(header, rows):
    wb = Workbook(); ws = wb.active; ws.append(header)
    for r in rows:
        ws.append(r)
    b = io.BytesIO(); wb.save(b); return b.getvalue()


# --- Master Item import robustness
class TestItemImport:
    def test_csv_cp1252_semicolon_nbsp_preserves_missing_cols(self, admin):
        csv = "Lane;Product;Type;ICS\xa0No.;T/T (detik)\nZT9;" + PROD + ";" + TYP["M1"] + ";" + ICS["M1"] + ";40\nZT9;" + PROD + ";" + TYP["M2"] + "\xa0;" + ICS["M2"] + ";45\n"
        b = csv.encode("cp1252")
        assert b"\xa0" in b
        p = upload(admin, f"{API}/import/items/preview", "items.csv", b)
        assert p.status_code == 200, p.text
        j = p.json()
        assert j["total"] == 2 and j["invalid"] == 0 and j["duplicates"] == 2, j
        c = upload(admin, f"{API}/import/items/confirm", "items.csv", b)
        assert c.status_code == 200, c.text
        assert c.json()["updated"] == 2 and c.json()["inserted"] == 0, c.json()
        it = mongo.items.find_one({"ics_no": ICS["M1"], "type": TYP["M1"]})
        assert it["tt"] == 40 and it["ics_name"] == "ZT NAME M1" and it["group"] == "GROUP 4"
        assert it["std_stock_min"] == 100 and it["std_stock_max"] == 300
        assert mongo.items.count_documents({"ics_no": ICS["M2"]}) == 1

    def test_xls_with_invalid_std_row_only_that_row_fails(self, admin):
        import xlwt
        wb = xlwt.Workbook(); ws = wb.add_sheet("s")
        hdr = ["Lane", "Product", "Type", "ICS No.", "STD STOCK MIN", "STD STOCK MAX"]
        data = [["ZT9", PROD, TYP["M1"], ICS["M1"], 60, 50], ["ZT9", PROD, TYP["M2"], ICS["M2"], 5, 40]]
        for i, h in enumerate(hdr):
            ws.write(0, i, h)
        for r, row in enumerate(data, 1):
            for i, v in enumerate(row):
                ws.write(r, i, v)
        b = io.BytesIO(); wb.save(b); b = b.getvalue()
        p = upload(admin, f"{API}/import/items/preview", "items.xls", b)
        assert p.status_code == 200, p.text
        assert p.json()["invalid"] == 1 and p.json()["total"] == 2, p.json()
        c = upload(admin, f"{API}/import/items/confirm", "items.xls", b)
        assert c.status_code == 200, c.text
        assert c.json()["updated"] == 1 and c.json()["skipped"] == 1, c.json()
        m1 = mongo.items.find_one({"ics_no": ICS["M1"]}); m2 = mongo.items.find_one({"ics_no": ICS["M2"]})
        assert m1["std_stock_min"] == 100 and m1["std_stock_max"] == 300
        assert m2["std_stock_min"] == 5 and m2["std_stock_max"] == 40 and m2["ics_name"] == "ZT NAME M2"

    def test_partial_std_merge_conflict_row_only(self, admin):
        # file only has STD STOCK MAX=50 while existing MIN=100 -> row should fail, not the whole request
        b = xlsx_bytes(["Lane", "Product", "Type", "ICS No.", "STD STOCK MAX"],
                       [["ZT9", PROD, TYP["M1"], ICS["M1"], 50], ["ZT9", PROD, TYP["M2"], ICS["M2"], 45]])
        c = upload(admin, f"{API}/import/items/confirm", "items.xlsx", b)
        assert c.status_code == 200, f"{c.status_code} {c.text}"
        m2 = mongo.items.find_one({"ics_no": ICS["M2"]})
        assert m2["std_stock_max"] == 45

    def test_xlsx_export_like(self, admin):
        hdr = ["Lane", "Product", "Type", "ICS No.", "ICS NAME", "GROUP", "STD STOCK MIN", "STD STOCK MAX", "T/T (detik)", "CAP/H",
               "T/T Assy (detik/unit)", "Kebutuhan Material per Unit Assy", "PROSES MESIN"]
        b = xlsx_bytes(hdr, [["ZT9", PROD, TYP["M1"], ICS["M1"], "ZT NAME M1", "GROUP 4", 100, 300, 36, 100, 10, 1, "INJECTION"]])
        p = upload(admin, f"{API}/import/items/preview", "items.xlsx", b)
        assert p.status_code == 200, p.text
        assert p.json()["invalid"] == 0 and p.json()["unknown_columns"] == [], p.json()


# --- Needs grid new columns
class TestNeedsGridCols:
    def test_achievement_and_actual_customer(self, admin):
        r = grow(admin, D2, "A1")
        assert r["actual_customer"] == 950
        assert abs(r["achievement_s3"] - 98.0) < 1e-6
        assert r["achievement_s1"] is None and r["achievement_s2"] is None
        assert grow(admin, D2, "H")["achievement_s3"] is None

    def test_patch_actual_customer(self, admin):
        r = admin.patch(f"{API}/needs-grid/cell", json={"date": D2, "ics_no": ICS["A1"], "type": TYP["A1"], "field": "actual_customer", "value": 951})
        assert r.status_code == 200, r.text
        assert r.json()["actual_customer"] == 951
        assert grow(admin, D2, "A1")["actual_customer"] == 951
        admin.patch(f"{API}/needs-grid/cell", json={"date": D2, "ics_no": ICS["A1"], "type": TYP["A1"], "field": "actual_customer", "value": 950})


# --- Needs import
NH = ["TANGGAL", "ICS NO", "TYPE", "PLAN CUSTOMER (ASSY)", "ACTUAL CUSTOMER (ASSY)", "PLAN S3", "ACTUAL S3", "STATUS MESIN S3", "BALANCE", "FOO"]


class TestNeedsImport:
    def file1(self):
        return xlsx_bytes(NH, [
            [D_IMP, ICS["B"], TYP["B"], 10, 5, 100, 90, "on", 1, "x"],
            ["01/04/2031", ICS["C"], TYP["C"], 20, None, 200, None, "DANDORI", None, None],
            ["abc", ICS["D"], TYP["D"], 1, 1, 1, 1, "ON", None, None],
            [D_IMP, "9999999999", "NOPE", 1, 1, 1, 1, "ON", None, None],
            [D_IMP, ICS["D"], TYP["D"], 1.5, 1, 1, 1, "ON", None, None],
            [D_IMP, ICS["E"], TYP["E"], -3, 1, 1, 1, "ON", None, None],
            [D_IMP, ICS["F"], TYP["F"], 1, 1, 1, 1, "XYZ", None, None],
            [D_IMP, ICS["B"], TYP["B"], 11, 6, 100, 90, "ON", None, None],
        ])

    def test_missing_header_400(self, admin):
        b = xlsx_bytes(["TANGGAL", "ICS NO", "PLAN S3"], [[D_IMP, ICS["B"], 1]])
        r = upload(admin, f"{API}/needs-grid/import/preview", "n.xlsx", b, {"mode": "add"})
        assert r.status_code == 400 and "TYPE" in r.text

    def test_readonly_403(self, assy):
        b = self.file1()
        assert upload(assy, f"{API}/needs-grid/import/preview", "n.xlsx", b, {"mode": "add"}).status_code == 403
        assert upload(assy, f"{API}/needs-grid/import/confirm", "n.xlsx", b, {"mode": "add"}).status_code == 403

    def test_preview_add_and_confirm_flow(self, admin):
        b = self.file1()
        p = upload(admin, f"{API}/needs-grid/import/preview", "n.xlsx", b, {"mode": "add"})
        assert p.status_code == 200, p.text
        j = p.json()
        assert j["counts"] == {"total": 8, "baru": 2, "diperbarui": 0, "dilewati": 0, "gagal": 6}, j["counts"]
        assert "FOO" in j["unknown_columns"] and "BALANCE" in j["reference_columns"]
        assert set(j["input_columns"]) >= {"plan_customer", "actual_customer", "plan_s3", "actual_s3", "status_mesin_s3"}
        acts = {r["row"]: r["action"] for r in j["rows"]}
        assert acts[2] == "baru" and acts[3] == "baru" and acts[9] == "gagal"
        assert j["rows"][1]["date"] == D_IMP
        c = upload(admin, f"{API}/needs-grid/import/confirm", "n.xlsx", b, {"mode": "add"})
        assert c.status_code == 200, c.text
        assert c.json()["counts"]["baru"] == 2 and len(c.json()["failed"]) == 6
        assert mongo.needs_entries.count_documents({"date": D_IMP}) == 2
        rb = grow(admin, D_IMP, "B")
        assert rb["plan_customer"] == 10 and rb["actual_customer"] == 5 and rb["status_mesin_s3"] == "ON"
        # add again -> dilewati
        p2 = upload(admin, f"{API}/needs-grid/import/preview", "n.xlsx", b, {"mode": "add"}).json()
        assert p2["counts"]["dilewati"] == 2 and p2["counts"]["baru"] == 0
        upload(admin, f"{API}/needs-grid/import/confirm", "n.xlsx", b, {"mode": "add"})
        assert grow(admin, D_IMP, "B")["plan_customer"] == 10
        # update with empty actual_customer -> keeps 5
        b2 = xlsx_bytes(NH[:5], [[D_IMP, ICS["B"], TYP["B"], 20, None], [D_IMP, ICS["D"], TYP["D"], 7, 3]])
        p3 = upload(admin, f"{API}/needs-grid/import/preview", "n2.xlsx", b2, {"mode": "update"}).json()
        assert p3["counts"]["diperbarui"] == 1 and p3["counts"]["baru"] == 1, p3["counts"]
        c3 = upload(admin, f"{API}/needs-grid/import/confirm", "n2.xlsx", b2, {"mode": "update"}).json()
        assert c3["counts"]["diperbarui"] == 1
        rb = grow(admin, D_IMP, "B")
        assert rb["plan_customer"] == 20 and rb["actual_customer"] == 5 and rb["plan_s3"] == 100
        assert mongo.needs_entries.count_documents({"date": D_IMP, "ics_no": ICS["B"]}) == 1
        assert mongo.needs_entries.count_documents({"date": D_IMP}) == 3

    def test_excel_serial_date(self, admin):
        # 2031-04-01 serial = 47939
        b = xlsx_bytes(["TANGGAL", "ICS NO", "TYPE", "PLAN S1"], [[47939, ICS["G"], TYP["G"], 3]])
        j = upload(admin, f"{API}/needs-grid/import/preview", "s.xlsx", b, {"mode": "add"}).json()
        assert j["rows"][0]["date"] == D_IMP, j["rows"][0]

    def test_template_export(self, admin):
        r = admin.get(f"{API}/needs-grid/import/template", params={"date": D2})
        assert r.status_code == 200
        ws = load_workbook(io.BytesIO(r.content)).active
        hdr = [c.value for c in ws[1]]
        assert "ACTUAL CUSTOMER (ASSY)" in hdr and "ACHIEVEMENT S3" in hdr
        assert hdr.index("ACTUAL CUSTOMER (ASSY)") == hdr.index("PLAN CUSTOMER (ASSY)") + 1
        assert ws.max_row - 1 == len(admin.get(f"{API}/needs-grid", params={"date": D2}).json())
        # round trip: exported file re-imports in update mode without failure for seeded rows
        p = upload(admin, f"{API}/needs-grid/import/preview", "t.xlsx", r.content, {"mode": "update"})
        assert p.status_code == 200, p.text
        assert p.json()["counts"]["gagal"] == 0, p.json()["counts"]


# --- Stock STATUS PART
class TestStockStatusPart:
    def test_status_part_matches_needs(self, admin):
        rows = [x for x in admin.get(f"{API}/smt-stock", params={"date_from": D1, "date_to": "2031-03-05"}).json() if x["ics_no"] in ALL_ICS]
        assert len(rows) == 12
        for x in rows:
            if x["date"] == "2031-03-05":
                assert x["status_part"] == "BELUM TERSEDIA"
                continue
            k = [kk for kk, v in ICS.items() if v == x["ics_no"]][0]
            assert x["status_part"] == grow(admin, x["date"], k)["status_part"], (k, x["date"])
        e = [x for x in rows if x["ics_no"] == ICS["E"]][0]
        assert e["status_part"] == "SHORTAGE"


# --- Dashboard
class TestDashboard:
    def get(self, admin, **p):
        r = admin.get(f"{API}/dashboard/summary", params={"date_from": D1, "date_to": D2, "product": PROD, **p})
        assert r.status_code == 200, r.text
        return r.json()

    def test_totals_chart(self, admin):
        j = self.get(admin)
        rp = j["resume"]["part_production"]
        assert rp["total_plan"] == 16000 and rp["act_prod"] == 14824 and rp["pct"] == 92.65, rp
        ra = j["resume"]["lamp_assy"]
        assert ra["total_plan"] == 15700 and ra["act_prod"] == 1450 and ra["pct"] == 9.24, ra
        tr = j["smt_trend"]
        assert [t["date"] for t in tr] == [D1, D2]
        assert tr[0]["plan"] == 600 and tr[0]["actual"] == 480
        assert tr[1]["plan"] == 15100 and tr[1]["actual"] == 14344

    def test_achievement_buckets(self, admin):
        a = self.get(admin)["resume"]["achievement"]
        assert all(v["total_plan"] == 7 for v in a.values()), a
        assert (a["gt97"]["act"], a["b96_97"]["act"], a["mid"]["act"], a["lt90"]["act"]) == (1, 2, 3, 1), a

    def test_shortage_counts(self, admin):
        s = self.get(admin)["resume"]["shortage"]
        assert s["total_part"] == 10 and s["with_status"] == 8
        assert (s["tidak_shortage"], s["potensi_shortage"], s["shortage"]) == (2, 3, 3), s
        assert s["latest_date"] == D2

    def test_top_shortage(self, admin):
        t = self.get(admin)["top_shortage"]
        assert t[0]["ics_no"] == ICS["A1b"] and t[0]["balance"] == -1990 and t[0]["ics_name"] == "ZT NAME A1b" and t[0]["type"] == TYP["A1b"]
        bal = [x["balance"] for x in t]
        assert bal == sorted(bal)
        f = [x for x in t if x["ics_no"] == ICS["F"]]
        assert not f or f[0]["date"] == D2

    def test_group_composition(self, admin):
        g = {x["group"]: x for x in self.get(admin)["group_composition"]}
        assert (g["GROUP 1"]["total_type"], g["GROUP 1"]["total_stock"], g["GROUP 1"]["shortage_type"]) == (3, 1510, 2), g["GROUP 1"]
        assert (g["GROUP 2"]["total_type"], g["GROUP 2"]["total_stock"], g["GROUP 2"]["shortage_type"]) == (3, 250, 0), g["GROUP 2"]
        assert (g["GROUP 3"]["total_type"], g["GROUP 3"]["total_stock"], g["GROUP 3"]["shortage_type"]) == (2, 777, 1), g["GROUP 3"]

    def test_date_filter(self, admin):
        j = self.get(admin, date_from=D2, date_to=D2)
        assert [t["date"] for t in j["smt_trend"]] == [D2]
        assert j["resume"]["part_production"]["total_plan"] == 15500

    def test_empty_period_null_pct(self, admin):
        j = self.get(admin, date_from="2035-01-01", date_to="2035-01-02")
        assert j["resume"]["part_production"]["pct"] is None and j["resume"]["lamp_assy"]["pct"] is None
        assert j["smt_trend"] == []
