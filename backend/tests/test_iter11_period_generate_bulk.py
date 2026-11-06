# Iteration 11: ACT STOCK = SHIFT 2 of D-1, needs-grid period+group filter, daily generate (manual+cron), checklist delete
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "part_production")]
SECRET = [l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if l.startswith("WEBHOOK_CRON_SECRET=")][0]
GRP = "ZTGRP11"
ICS = {k: f"99000011{n:02d}" for n, k in enumerate(["A", "B", "C"], 1)}
TYP = {k: f"ZT11 {k}" for k in ICS}
D, PREV = "2033-02-10", "2033-02-09"
GEN_DATE = "2033-01-10"
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
    mongo.smt_stock.delete_many({"date": GEN_DATE})
    mongo.generate_logs.delete_many({"date": GEN_DATE})


@pytest.fixture(scope="module")
def admin():
    return login("admin", "admin123")


@pytest.fixture(scope="module")
def assy():
    return login("assy", "password123")


@pytest.fixture(scope="module")
def smt():
    return login("smt", "password123")


@pytest.fixture(scope="module", autouse=True)
def seed(admin):
    cleanup()
    base_items = mongo.items.count_documents({})
    for k, ics in ICS.items():
        r = admin.post(f"{API}/items", json={"lane": "ZT11", "product": "ZTPROD11", "type": TYP[k], "ics_no": ics, "ics_name": f"ZT {k}",
                                            "group": GRP, "std_stock_min": 0, "std_stock_max": 20, "proses_mesin": "INJECTION"})
        assert r.status_code == 200, r.text
    yield base_items
    cleanup()
    assert mongo.items.count_documents({}) == base_items


def stock(admin, k, date, shift, g1):
    r = admin.post(f"{API}/smt-stock", json={"date": date, "shift": shift, "lane": "ZT11", "product": "ZTPROD11", "type": TYP[k],
                                             "ics_no": ICS[k], "group1": g1})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def grow(s, k, date=D):
    rows = [x for x in s.get(f"{API}/needs-grid", params={"date_from": date, "date_to": date}).json()
            if x["ics_no"] == ICS[k] and x["type"] == TYP[k]]
    assert len(rows) == 1, rows
    return rows[0]


# --- ACT STOCK JAM 01:00 = TOTAL SHIFT 2 of D-1
class TestActStock:
    def test_shift2_prev_day_only(self, admin):
        sid = stock(admin, "A", PREV, "SHIFT 2", 70)
        stock(admin, "A", PREV, "SHIFT 3", 1000)
        stock(admin, "A", PREV, "SHIFT 1", 2000)
        stock(admin, "A", D, "SHIFT 2", 3000)
        stock(admin, "A", D, "SHIFT 3", 4000)
        stock(admin, "B", D, "SHIFT 3", 50)  # same-day SHIFT 3 not used -> None
        r = grow(admin, "A")
        assert r["act_stock"] == 70 and r["id"] == f"{D}|{ICS['A']}|{TYP['A']}"
        assert grow(admin, "B")["act_stock"] is None
        # D+1 uses SHIFT 2 of D (3000)
        assert grow(admin, "A", "2033-02-11")["act_stock"] == 3000
        # edit -> reflects
        assert admin.patch(f"{API}/smt-stock/{sid}/cell", json={"field": "group1", "value": 15}).status_code == 200
        r = grow(admin, "A")
        assert r["act_stock"] == 15 and r["level_stock"] == 0.75

    def test_status_part_and_stock_page(self, admin):
        admin.patch(f"{API}/needs-grid/cell", json={"date": D, "ics_no": ICS["A"], "type": TYP["A"], "field": "plan_customer", "value": 20})
        r = grow(admin, "A")
        assert r["balance"] == -5 and r["status_part"] == "SHORTAGE"
        rows = [x for x in admin.get(f"{API}/smt-stock", params={"date_from": D, "date_to": D}).json() if x["ics_no"] == ICS["A"]]
        assert rows and all(x["status_part"] == "SHORTAGE" for x in rows)
        dash = admin.get(f"{API}/dashboard/summary", params={"date_from": D, "date_to": D, "product": "ZTPROD11"}).json()
        assert any(t["ics_no"] == ICS["A"] and t["act_stock"] == 15 and t["balance"] == -5 for t in dash["top_shortage"]), dash["top_shortage"]


# --- Period + group filter
class TestPeriod:
    def test_period_rows(self, admin):
        n = mongo.items.count_documents({})
        r = admin.get(f"{API}/needs-grid", params={"date_from": "2033-02-08", "date_to": "2033-02-10"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= n * 3
        assert {x["date"] for x in data} == {"2033-02-08", "2033-02-09", "2033-02-10"}
        assert len({x["id"] for x in data}) == len(data)

    def test_group_filter(self, admin):
        data = admin.get(f"{API}/needs-grid", params={"date_from": "2033-02-09", "date_to": "2033-02-10", "group": GRP}).json()
        assert len(data) == 6 and all(x["group"] == GRP for x in data)
        assert len(admin.get(f"{API}/needs-grid", params={"date_from": D, "date_to": D, "group": "ALL"}).json()) >= mongo.items.count_documents({})

    @pytest.mark.parametrize("p", [{"date_from": "2033-01-01", "date_to": "2033-02-01"}, {"date_from": "2033-02-10", "date_to": "2033-02-09"},
                                   {"date_from": "abc", "date_to": "2033-02-09"}])
    def test_invalid(self, admin, p):
        assert admin.get(f"{API}/needs-grid", params=p).status_code == 400

    def test_31_days_ok(self, admin):
        assert admin.get(f"{API}/needs-grid", params={"date_from": "2033-01-01", "date_to": "2033-01-31", "group": GRP}).status_code == 200

    def test_master_groups_meta(self, admin):
        assert GRP in admin.get(f"{API}/meta/options").json().get("master_groups", [])

    def test_stock_group_filter(self, admin):
        rows = admin.get(f"{API}/smt-stock", params={"date_from": PREV, "date_to": D, "group": GRP}).json()
        assert rows and all(x["group"] == GRP for x in rows)


# --- Generate (manual + cron)
class TestGenerate:
    def test_manual_generate_idempotent(self, admin):
        keep = stock(admin, "C", GEN_DATE, "SHIFT 1", 9)
        expected = 3 * len({(i.get("ics_no"), i.get("type")) for i in mongo.items.find({}) if i.get("ics_no")})
        r = admin.post(f"{API}/smt-stock/generate", json={"date": GEN_DATE})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "SUCCESS" and j["expected"] == expected and j["inserted"] == expected - 1 and j["existing"] == 1, j
        assert mongo.smt_stock.count_documents({"date": GEN_DATE}) == expected
        j2 = admin.post(f"{API}/smt-stock/generate", json={"date": GEN_DATE}).json()
        assert j2["inserted"] == 0 and j2["existing"] == expected
        assert mongo.smt_stock.count_documents({"date": GEN_DATE}) == expected
        k = mongo.smt_stock.find_one({"_id": __import__("bson").ObjectId(keep)})
        assert k["group1"] == 9 and k["total"] == 9 and not k.get("generated")
        g = mongo.smt_stock.find_one({"date": GEN_DATE, "ics_no": ICS["A"], "shift": "SHIFT 2"})
        assert g["total"] is None and g["group1"] is None
        # empty generated SHIFT 2 -> act_stock next day null
        assert grow(admin, "A", "2033-01-11")["act_stock"] is None
        logs = admin.get(f"{API}/smt-stock/generate-logs").json()
        assert any(l["date"] == GEN_DATE and l["status"] == "SUCCESS" for l in logs)
        assert "_id" not in logs[0]

    def test_non_admin_forbidden(self, smt, assy):
        assert smt.post(f"{API}/smt-stock/generate", json={"date": GEN_DATE}).status_code == 403
        assert assy.post(f"{API}/smt-stock/generate", json={"date": GEN_DATE}).status_code == 403

    def test_bad_date(self, admin):
        assert admin.post(f"{API}/smt-stock/generate", json={"date": "2033-13-01"}).status_code == 400

    def test_unique_index(self):
        assert "uniq_stock_key" in mongo.smt_stock.index_information()

    def test_cron_auth(self):
        assert requests.post(f"{API}/cron/daily-generate").status_code == 401
        assert requests.post(f"{API}/cron/daily-generate", headers={"Authorization": "Bearer wrong"}).status_code == 401

    def test_cron_accept_duplicate(self):
        rid = f"TEST_{uuid.uuid4().hex}"
        h = {"Authorization": f"Bearer {SECRET}", "X-Webhook-Id": rid}
        r = requests.post(f"{API}/cron/daily-generate", headers=h, json={})
        assert r.status_code == 200 and r.json()["status"] == "accepted", r.text
        r2 = requests.post(f"{API}/cron/daily-generate", headers=h, json={})
        assert r2.json()["status"] == "duplicate"
        log = None
        for _ in range(20):
            time.sleep(1)
            log = mongo.generate_logs.find_one({"run_id": rid})
            if log and log.get("status") != "RUNNING":
                break
        assert log and log["status"] == "SUCCESS", log
        # today's rows: no duplicates
        today = log["date"]
        pipeline = [{"$match": {"date": today}}, {"$group": {"_id": {"i": "$ics_no", "t": "$type", "s": "$shift"}, "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]
        assert list(mongo.smt_stock.aggregate(pipeline)) == []
        mongo.cron_runs.delete_one({"_id": rid})
        mongo.generate_logs.delete_one({"run_id": rid})


# --- Checklist delete
class TestBulkDelete:
    def test_stock_bulk_delete(self, admin, assy):
        ids = [stock(admin, "B", "2033-03-01", sh, 1) for sh in ("SHIFT 3", "SHIFT 1", "SHIFT 2")]
        assert assy.post(f"{API}/smt-stock/bulk-delete", json={"ids": ids[:1]}).status_code == 403
        assert admin.post(f"{API}/smt-stock/bulk-delete", json={"ids": []}).status_code == 400
        r = admin.post(f"{API}/smt-stock/bulk-delete", json={"ids": ids[:2]})
        assert r.status_code == 200 and r.json()["deleted"] == 2
        left = [x["id"] for x in admin.get(f"{API}/smt-stock", params={"date_from": "2033-03-01", "date_to": "2033-03-01"}).json() if x["ics_no"] == ICS["B"]]
        assert left == [ids[2]]
        assert mongo.audit_log.count_documents({"module": "smt_stock", "action": "DELETE", "record_id": {"$in": ids[:2]}}) == 2
        r = admin.post(f"{API}/smt-stock/bulk-delete", json={"ids": [ids[2]]})
        assert r.json()["deleted"] == 1

    def test_needs_clear(self, admin, assy):
        for k in ("B", "C"):
            assert admin.patch(f"{API}/needs-grid/cell", json={"date": D, "ics_no": ICS[k], "type": TYP[k], "field": "plan_s1", "value": 7}).status_code == 200
        row = {"date": D, "ics_no": ICS["B"], "type": TYP["B"]}
        assert assy.post(f"{API}/needs-grid/clear", json={"rows": [row]}).status_code == 403
        assert admin.post(f"{API}/needs-grid/clear", json={"rows": []}).status_code == 400
        r = admin.post(f"{API}/needs-grid/clear", json={"rows": [row]})
        assert r.status_code == 200 and r.json()["cleared"] == 1
        b, c = grow(admin, "B"), grow(admin, "C")
        assert b["plan_s1"] is None and b["master_found"] and c["plan_s1"] == 7
        assert mongo.audit_log.count_documents({"module": "production_needs", "action": "DELETE", "ics_no": ICS["B"], "date": D}) >= 1


class TestRegression:
    @pytest.mark.parametrize("ep", ["/dashboard/summary", "/items", "/audit", "/smt-stock", "/needs-grid", "/meta/options", "/smt-stock/generate-logs"])
    def test_endpoints(self, admin, ep):
        assert admin.get(f"{API}{ep}").status_code == 200
