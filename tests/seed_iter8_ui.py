import os, sys, requests
from pymongo import MongoClient
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
m = MongoClient("mongodb://localhost:27017")["part_production"]
ICS = ["9900000091", "9900000092"]
if sys.argv[1] == "clean":
    print(m.smt_stock.delete_many({"ics_no": {"$in": ICS}}).deleted_count, m.needs_entries.delete_many({"ics_no": {"$in": ICS}}).deleted_count, m.items.delete_many({"ics_no": {"$in": ICS}}).deleted_count)
    sys.exit()
s = requests.Session()
r = s.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}).json()
s.headers["Authorization"] = "Bearer " + (r.get("token") or r.get("access_token"))
base = {"lane": "AAZT", "product": "REGULER", "proses_mesin": "INJECTION", "group": "GROUP 1", "tt_assy": 36, "material_per_unit": 1}
print(s.post(f"{API}/items", json={**base, "ics_no": ICS[0], "type": "ZT UI A", "ics_name": "ZT UI A", "std_stock_min": 0, "std_stock_max": 20}).status_code)
print(s.post(f"{API}/items", json={**base, "ics_no": ICS[1], "type": "ZT UI B", "ics_name": "ZT UI B"}).status_code)
r = s.post(f"{API}/smt-stock", json={"date": "2030-02-01", "shift": "SHIFT 3", "lane": "AAZT", "product": "REGULER", "type": "ZT UI A", "ics_no": ICS[0], "group1": 40})
print(r.status_code, r.json().get("id"))
