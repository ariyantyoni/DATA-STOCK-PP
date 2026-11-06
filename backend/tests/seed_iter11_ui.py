# Iteration 11 UI seed / cleanup: temp ZT items + stock rows + needs entries on 2033-03-05 (usage: python seed_iter11_ui.py [seed|clean])
import os
import sys
import requests
from pymongo import MongoClient

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
mongo = MongoClient("mongodb://localhost:27017")["part_production"]
ICS = [f"99000012{n:02d}" for n in range(1, 4)]
D = "2033-03-05"


def clean():
    for c in ("smt_stock", "needs_entries", "items"):
        mongo[c].delete_many({"ics_no": {"$in": ICS}})


def seed():
    clean()
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}).json()["token"]
    for i, ics in enumerate(ICS):
        t = f"ZTUI {i}"
        assert s.post(f"{API}/items", json={"lane": "ZTUI", "product": "ZTPRODUI", "type": t, "ics_no": ics, "ics_name": f"ZTUI {i}",
                                            "group": "ZTGRPUI", "std_stock_min": 0, "std_stock_max": 20, "proses_mesin": "INJECTION"}).status_code == 200
        for sh in ("SHIFT 3", "SHIFT 1", "SHIFT 2"):
            assert s.post(f"{API}/smt-stock", json={"date": D, "shift": sh, "lane": "ZTUI", "product": "ZTPRODUI", "type": t, "ics_no": ics, "group1": 10 + i}).status_code == 200
        assert s.patch(f"{API}/needs-grid/cell", json={"date": D, "ics_no": ics, "type": t, "field": "plan_s1", "value": 5 + i}).status_code == 200
    print("seeded")


if __name__ == "__main__":
    (clean if sys.argv[-1] == "clean" else seed)()
