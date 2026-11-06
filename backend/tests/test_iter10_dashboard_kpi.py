# Iteration 10: Dashboard KPI live computation (part/assy production, item shortage, achievement buckets, top shortage, group composition)
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "part_production")]
PROD = "ZTPROD10"
D1, D2 = "2032-03-01", "2032-03-02"
P = {"date_from": D1, "date_to": D2}
PP = {**P, "product": PROD}

# key: (type, group, std_min, std_max)
ITEMS = {
    "A89": ("ZT10 A89", "GROUP 1", 100, 300), "A90": ("ZT10 A90", "GROUP 1", 100, 300),
    "A96": ("ZT10 A96", "GROUP 2", 100, 300), "A965": ("ZT10 A965", "GROUP 2", 100, 300),
    "A97": ("ZT10 A97", "GROUP 3", 100, 300), "A98a": ("ZT10 A98", "GROUP 3", 100, 300),
    "A98b": ("ZT10 A98", "GROUP 3", 100, 300), "A0": ("ZT10 A0", "GROUP 4", 100, 300),
    "AE": ("ZT10 AE", "GROUP 4", 100, 300),
    "S1": ("ZT10 S1", "GROUP 5", 100, 300), "S2": ("ZT10 S2", "GROUP 5", 100, 300),
    "W1": ("ZT10 W", "GROUP 1", 100, 300), "W2": ("ZT10 W", "GROUP 1", 100, 300),
    "L": ("ZT10 L", "GROUP 2", 100, 300), "N": ("ZT10 N", "GROUP 6", None, None),
}
ICS = {k: f"99000010{n:02d}" for n, k in enumerate(ITEMS, 1)}
ALL_ICS = list(ICS.values())
SH = (3, 1, 2)


def sday(d, n):
    from datetime import datetime, timedelta
    return (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=n)).strftime("%Y-%m-%d")


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


def cell(s, k, date, field, value):
    r = s.patch(f"{API}/needs-grid/cell", json={"date": date, "ics_no": ICS[k], "type": ITEMS[k][0], "field": field, "value": value})
    assert r.status_code == 200, r.text
    return r.json()


def summ(s, params=PP):
    r = s.get(f"{API}/dashboard/summary", params=params)
    assert r.status_code == 200, r.text
    return r.json()


STOCK_IDS = {}


@pytest.fixture(scope="module")
def admin():
    return login("admin", "admin123")


@pytest.fixture(scope="module", autouse=True)
def seed(admin):
    cleanup()
    base_items = mongo.items.count_documents({})
    base_snapshot = sorted((d.get("ics_no"), d.get("type"), d.get("std_stock_min"), d.get("std_stock_max")) for d in mongo.items.find({}))
    for k, (typ, grp, mn, mx) in ITEMS.items():
        body = {"lane": "ZT10", "product": PROD, "type": typ, "ics_no": ICS[k], "ics_name": f"ZT NAME {k}", "group": grp,
                "tt": 36, "proses_mesin": "INJECTION"}
        if mn is not None:
            body.update(std_stock_min=mn, std_stock_max=mx)
        r = admin.post(f"{API}/items", json=body)
        assert r.status_code == 200, r.text
    # achievement data
    cell(admin, "A89", D1, "plan_s3", 1000); cell(admin, "A89", D1, "actual_s3", 890)
    cell(admin, "A90", D1, "plan_s1", 1000); cell(admin, "A90", D1, "actual_s1", 900)
    cell(admin, "A96", D2, "plan_s2", 1000); cell(admin, "A96", D2, "actual_s2", 960)
    cell(admin, "A965", D2, "plan_s3", 600); cell(admin, "A965", D2, "plan_s1", 400)
    cell(admin, "A965", D2, "actual_s3", 600); cell(admin, "A965", D2, "actual_s1", 365)
    cell(admin, "A97", D2, "plan_s3", 1000); cell(admin, "A97", D2, "actual_s3", 970)
    cell(admin, "A98a", D1, "plan_s3", 500); cell(admin, "A98a", D1, "actual_s3", 490)
    cell(admin, "A98b", D2, "plan_s1", 500); cell(admin, "A98b", D2, "actual_s2", 490)
    cell(admin, "A0", D2, "plan_s3", 0); cell(admin, "A0", D2, "actual_s3", 50)
    cell(admin, "AE", D2, "actual_s1", 30)
    # stock & customer plans for shortage
    stocks = [("S1", D2, "SHIFT 3", 1000), ("S2", D2, "SHIFT 3", 150), ("W1", D2, "SHIFT 3", 1000), ("W2", D2, "SHIFT 3", 10),
              ("L", D1, "SHIFT 3", 0), ("L", D2, "SHIFT 3", 1000), ("N", D2, "SHIFT 3", 500), ("S1", D2, "SHIFT 1", 777),
              ("A89", D1, "SHIFT 1", 40)]  # iter11: A89 distractor (not SHIFT 2 of D-1 for any graded day)
    for k, d, sh, tot in stocks:
        r = admin.post(f"{API}/smt-stock", json={"date": d, "shift": sh, "lane": "ZT10", "product": PROD, "type": ITEMS[k][0],
                                                 "ics_no": ICS[k], "group1": tot})
        assert r.status_code == 200, r.text
        STOCK_IDS[(k, d, sh)] = r.json()["id"]
    # iter11: ACT STOCK D = TOTAL SHIFT 2 of D-1 -> mirror each SHIFT 3 seed to SHIFT 2 of previous day
    for k, d, sh, tot in stocks:
        if sh == "SHIFT 3":
            pd_ = sday(d, -1)
            r = admin.post(f"{API}/smt-stock", json={"date": pd_, "shift": "SHIFT 2", "lane": "ZT10", "product": PROD, "type": ITEMS[k][0],
                                                     "ics_no": ICS[k], "group1": tot})
            assert r.status_code == 200, r.text
            STOCK_IDS[(k, pd_, "SHIFT 2")] = r.json()["id"]
    cell(admin, "S1", D2, "plan_customer", 100)   # bal 900 -> TIDAK
    cell(admin, "S2", D2, "plan_customer", 100)   # bal 50 -> POTENSI
    cell(admin, "W1", D2, "plan_customer", 100)   # bal 900 TIDAK
    cell(admin, "W2", D2, "plan_customer", 100)   # bal -90 SHORTAGE -> type W worst = SHORTAGE
    cell(admin, "L", D1, "plan_customer", 100)    # D1 bal -100 SHORTAGE
    cell(admin, "L", D2, "plan_customer", 100)    # D2 bal 900 TIDAK (latest)
    cell(admin, "N", D2, "plan_customer", 100)    # STD BELUM DISET
    yield
    cleanup()
    assert mongo.items.count_documents({}) == base_items
    assert sorted((d.get("ics_no"), d.get("type"), d.get("std_stock_min"), d.get("std_stock_max")) for d in mongo.items.find({})) == base_snapshot


# ---------- independent reference implementation (pymongo) ----------
def num(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except Exception:
        return 0.0


def reference(date_from, date_to, product=None):
    items = list(mongo.items.find({}))
    imap = {(i.get("ics_no"), i.get("type")): i for i in items}
    if product:
        items = [i for i in items if i.get("product") == product]
    q = {"date": {"$gte": date_from, "$lte": date_to}}
    ents = {(e["date"], e["ics_no"], e["type"]): e for e in mongo.needs_entries.find(q)}
    stocks = list(mongo.smt_stock.find(q))
    s3 = {}
    qa = {"date": {"$gte": sday(date_from, -1), "$lte": sday(date_to, -1)}, "shift": "SHIFT 2"}
    for s in sorted(mongo.smt_stock.find(qa), key=lambda x: x.get("updated_at") or ""):
        if s.get("total") is None:
            continue
        s3[(sday(s["date"], 1), s["ics_no"], s["type"])] = num(s.get("total"))
    rows = []
    for key in set(ents) | set(s3):
        d, i, t = key
        it = imap.get((i, t))
        if not it or (product and it.get("product") != product):
            continue
        e = ents.get(key, {})
        stk = s3.get(key)
        bal = None if stk is None else round(stk - num(e.get("plan_customer")) + sum(num(e.get(f"actual_s{x}")) for x in SH), 1)
        mn, mx = it.get("std_stock_min"), it.get("std_stock_max")
        st = None
        if bal is not None:
            st = "SHORTAGE" if bal <= 0 else ("STD BELUM DISET" if mn is None or mx is None else
                                              ("POTENSI SHORTAGE" if bal <= (mn + mx) / 2 else "TIDAK SHORTAGE"))
        rows.append(dict(date=d, ics_no=i, type=t, e=e, balance=bal, status=st, group=(it.get("group") or "").strip()))
    pplan = sum(num(r["e"].get(f"plan_s{x}")) for r in rows for x in SH)
    pact = sum(num(r["e"].get(f"actual_s{x}")) for r in rows for x in SH)
    aplan = sum(num(r["e"].get("plan_customer")) for r in rows)
    aact = sum(num(r["e"].get("actual_customer")) for r in rows)
    pct = lambda a, p: round(a / p * 100, 2) if p else None
    ta = {}
    for r in rows:
        v = ta.setdefault(r["type"], [0.0, 0.0])
        v[0] += sum(num(r["e"].get(f"plan_s{x}")) for x in SH); v[1] += sum(num(r["e"].get(f"actual_s{x}")) for x in SH)
    planned = {t: a / p * 100 for t, (p, a) in ta.items() if p > 0}
    bk = {"gt97": [], "b96_97": [], "mid": [], "lt90": []}
    for t, a in planned.items():
        bk["gt97" if a > 97 else "b96_97" if a > 96 else "mid" if a >= 90 else "lt90"].append(a)
    rank = {"SHORTAGE": 3, "POTENSI SHORTAGE": 2, "TIDAK SHORTAGE": 1, "STD BELUM DISET": 0}
    mtypes = {i.get("type") for i in items if i.get("type")}
    latest = {}
    for r in rows:
        if not r["status"]:
            continue
        c = latest.get(r["type"])
        if not c or r["date"] > c[0] or (r["date"] == c[0] and rank[r["status"]] > rank[c[1]]):
            latest[r["type"]] = (r["date"], r["status"])
    sv = [v[1] for t, v in latest.items() if t in mtypes]
    last = {}
    for r in rows:
        if r["balance"] is None:
            continue
        k = (r["ics_no"], r["type"])
        if k not in last or r["date"] > last[k]["date"]:
            last[k] = r
    top = sorted([r for r in last.values() if r["balance"] <= 0], key=lambda x: x["balance"])[:10]
    so = {"SHIFT 3": 0, "SHIFT 1": 1, "SHIFT 2": 2}
    ig = {(i.get("ics_no"), i.get("type")): (i.get("group") or "").strip() for i in items}
    ls = {}
    for s in stocks:
        k = (s.get("ics_no"), s.get("type"))
        if k not in ig:
            continue
        o = (s.get("date") or "", so.get(s.get("shift"), -1))
        if k not in ls or o > ls[k][0]:
            ls[k] = (o, num(s.get("total")))
    groups = {}
    for g in {f"GROUP {i}" for i in range(1, 7)} | {g for g in ig.values() if g}:
        ks = [k for k in ls if ig[k] == g]
        groups[g] = (len({k[1] for k in ks}), sum(ls[k][1] for k in ks))
    return dict(part=(pplan, pact, pct(pact, pplan)), assy=(aplan, aact, pct(aact, aplan)),
                ach={k: (len(planned), len(v)) for k, v in bk.items()},
                ach_avg={k: (round(sum(v) / len(v), 2) if v else None) for k, v in bk.items()},
                short=(len(mtypes), sv.count("TIDAK SHORTAGE"), sv.count("POTENSI SHORTAGE"), sv.count("SHORTAGE"), len(sv)),
                top=[(r["ics_no"], r["type"], r["balance"]) for r in top], groups=groups)


def compare(api, ref):
    r = api["resume"]
    assert (r["part_production"]["total_plan"], r["part_production"]["act_prod"], r["part_production"]["pct"]) == ref["part"]
    assert (r["lamp_assy"]["total_plan"], r["lamp_assy"]["act_prod"], r["lamp_assy"]["pct"]) == ref["assy"]
    for k, (tp, act) in ref["ach"].items():
        assert r["achievement"][k]["total_plan"] == tp and r["achievement"][k]["act"] == act, k
        assert r["achievement"][k]["average"] == ref["ach_avg"][k], k
    s = r["shortage"]
    assert (s["total_part"], s["tidak_shortage"], s["potensi_shortage"], s["shortage"], s["with_status"]) == ref["short"]
    assert s["with_status"] + s["no_status"] == s["total_part"]
    assert [(t["ics_no"], t["type"], t["balance"]) for t in api["top_shortage"]] == ref["top"]
    g = {x["group"]: (x["total_type"], x["total_stock"]) for x in api["group_composition"]}
    assert g == ref["groups"]


# ---------- tests ----------
class TestPartAndAssy:
    def test_part_production_totals(self, admin):
        d = summ(admin)["resume"]["part_production"]
        plan = 1000 * 6 + 0
        act = 890 + 900 + 960 + 965 + 970 + 980 + 50 + 30
        assert d["total_plan"] == plan and d["act_prod"] == act
        assert d["pct"] == round(act / plan * 100, 2)

    def test_actual_delta(self, admin):
        before = summ(admin)["resume"]["part_production"]
        cell(admin, "A89", D2, "actual_s1", 25)
        after = summ(admin)["resume"]["part_production"]
        assert after["act_prod"] - before["act_prod"] == 25 and after["total_plan"] == before["total_plan"]
        assert after["pct"] == round(after["act_prod"] / after["total_plan"] * 100, 2)
        cell(admin, "A89", D2, "actual_s1", None)
        assert summ(admin)["resume"]["part_production"]["act_prod"] == before["act_prod"]

    def test_lamp_assy_independent(self, admin):
        before = summ(admin)["resume"]
        cell(admin, "A90", D1, "plan_customer", 800)
        cell(admin, "A90", D1, "actual_customer", 600)
        after = summ(admin)["resume"]
        assert after["lamp_assy"]["total_plan"] - before["lamp_assy"]["total_plan"] == 800
        assert after["lamp_assy"]["act_prod"] - before["lamp_assy"]["act_prod"] == 600
        assert after["lamp_assy"]["pct"] == round(after["lamp_assy"]["act_prod"] / after["lamp_assy"]["total_plan"] * 100, 2)
        assert after["part_production"] == before["part_production"]

    def test_pct_null_when_no_plan(self, admin):
        d = summ(admin, {"date_from": "2032-05-01", "date_to": "2032-05-02", "product": PROD})["resume"]
        assert d["part_production"]["pct"] is None and d["lamp_assy"]["pct"] is None


class TestAchievement:
    def test_buckets(self, admin):
        a = summ(admin)["resume"]["achievement"]
        assert {k: a[k]["act"] for k in a} == {"gt97": 1, "b96_97": 2, "mid": 2, "lt90": 1}
        assert all(a[k]["total_plan"] == 6 for k in a)
        assert a["lt90"]["average"] == 89.0 and a["gt97"]["average"] == 98.0
        assert a["mid"]["average"] == 93.0 and a["b96_97"]["average"] == 96.75


class TestShortage:
    def test_initial_status(self, admin):
        s = summ(admin)["resume"]["shortage"]
        types = len({v[0] for v in ITEMS.values()})
        assert s["total_part"] == types
        # S1 TIDAK, S2 POTENSI, W SHORTAGE(worst), L TIDAK(latest), N STD BELUM DISET, A89 (no SHIFT3) none
        assert (s["tidak_shortage"], s["potensi_shortage"], s["shortage"], s["std_belum_diset"]) == (2, 1, 1, 1)
        assert s["with_status"] == 5 and s["no_status"] == types - 5

    def test_total_part_all_products(self, admin):
        s = summ(admin, P)["resume"]["shortage"]
        assert s["total_part"] == len(mongo.items.distinct("type"))
        assert s["tidak_shortage"] + s["potensi_shortage"] + s["shortage"] <= s["total_part"]

    def test_move_to_shortage_via_stock(self, admin):
        r = admin.patch(f"{API}/smt-stock/{STOCK_IDS[('S1', D1, 'SHIFT 2')]}/cell", json={"field": "group1", "value": 50})
        assert r.status_code == 200, r.text
        s = summ(admin)["resume"]["shortage"]
        assert (s["tidak_shortage"], s["potensi_shortage"], s["shortage"]) == (1, 1, 2)
        top = summ(admin)["top_shortage"]
        assert any(t["ics_no"] == ICS["S1"] and t["balance"] == -50 for t in top)

    def test_move_via_plan_customer(self, admin):
        cell(admin, "S2", D2, "plan_customer", 10)  # bal 140 -> still POTENSI
        cell(admin, "S2", D2, "plan_customer", 0)   # bal 150 POTENSI
        cell(admin, "S2", D2, "actual_s3", 100)     # bal 250 -> TIDAK
        s = summ(admin)["resume"]["shortage"]
        assert (s["tidak_shortage"], s["potensi_shortage"], s["shortage"]) == (2, 0, 2)
        cell(admin, "S2", D2, "actual_s3", None); cell(admin, "S2", D2, "plan_customer", 100)


class TestTopShortage:
    def test_only_nonpositive_sorted(self, admin):
        top = summ(admin)["top_shortage"]
        bals = [t["balance"] for t in top]
        assert all(b is not None and b <= 0 for b in bals) and bals == sorted(bals)
        assert [t["ics_no"] for t in top] == [ICS["W2"], ICS["S1"]]  # -90, -50 ; L D1 (-100) superseded by D2
        for f in ("type", "product", "ics_no", "ics_name", "balance"):
            assert f in top[0]

    def test_order_change_and_disappear(self, admin):
        r = admin.patch(f"{API}/smt-stock/{STOCK_IDS[('S1', D1, 'SHIFT 2')]}/cell", json={"field": "group1", "value": 0})
        assert r.status_code == 200
        top = summ(admin)["top_shortage"]
        assert [t["ics_no"] for t in top] == [ICS["S1"], ICS["W2"]]
        cell(admin, "W2", D2, "plan_customer", 0)  # bal 10 -> disappears
        top = summ(admin)["top_shortage"]
        assert [t["ics_no"] for t in top] == [ICS["S1"]]

    def test_empty_period(self, admin):
        assert summ(admin, {"date_from": "2032-05-01", "date_to": "2032-05-02"})["top_shortage"] == []


class TestGroupComposition:
    def test_groups_and_update(self, admin):
        g = {x["group"]: x for x in summ(admin)["group_composition"]}
        for i in range(1, 7):
            assert f"GROUP {i}" in g
        before = g["GROUP 5"]["total_stock"]
        r = admin.patch(f"{API}/smt-stock/{STOCK_IDS[('S2', D2, 'SHIFT 3')]}/cell", json={"field": "group2", "value": 33})
        assert r.status_code == 200
        g2 = {x["group"]: x for x in summ(admin)["group_composition"]}
        assert g2["GROUP 5"]["total_stock"] == before + 33
        assert g2["GROUP 5"]["total_type"] == 2
        # S1 latest record is SHIFT 1 (777) not SHIFT 3
        assert g2["GROUP 6"]["total_type"] == 1 and g2["GROUP 6"]["total_stock"] == 500
        # group 1: W (two ICS: 1000 + 10) + A89 D1 SHIFT2 40 -> 2 types
        assert g2["GROUP 1"]["total_type"] == 2 and g2["GROUP 1"]["total_stock"] == 1050

    def test_groups_present_empty_period(self, admin):
        g = [x["group"] for x in summ(admin, {"date_from": "2032-05-01", "date_to": "2032-05-02"})["group_composition"]]
        assert all(f"GROUP {i}" in g for i in range(1, 7))


class TestReconciliation:
    def test_product_filter(self, admin):
        compare(summ(admin), reference(D1, D2, PROD))

    def test_all_products(self, admin):
        compare(summ(admin, P), reference(D1, D2))

    def test_single_day(self, admin):
        compare(summ(admin, {"date_from": D1, "date_to": D1, "product": PROD}), reference(D1, D1, PROD))

    def test_no_nan(self, admin):
        import json
        txt = json.dumps(summ(admin))
        assert "NaN" not in txt and "Infinity" not in txt
