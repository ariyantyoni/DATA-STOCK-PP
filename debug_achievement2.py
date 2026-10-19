#!/usr/bin/env python3
"""Debug achievement categories test - run in isolation"""

import requests

BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
USERNAME = "admin"
PASSWORD = "admin123"

created_ids = []

def login():
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    return resp.json()["token"]

def get_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def create_production_record(token, data):
    headers = get_headers(token)
    resp = requests.post(f"{BASE_URL}/smt-production", json=data, headers=headers)
    if resp.status_code == 200:
        record_id = resp.json().get("id")
        created_ids.append(record_id)
        return record_id
    else:
        raise Exception(f"Failed: {resp.status_code} {resp.text}")

token = login()
headers = get_headers(token)

test_date = "2026-01-20"

# Get 3 different master items
resp = requests.get(f"{BASE_URL}/items?product=REGULER", headers=headers)
items = resp.json()[:3]

print(f"Using 3 items:")
print(f"  Item 0: type={items[0]['type']}, ics_no={items[0]['ics_no']}")
print(f"  Item 1: type={items[1]['type']}, ics_no={items[1]['ics_no']}")
print(f"  Item 2: type={items[2]['type']}, ics_no={items[2]['ics_no']}")

# Type A: ~99% achievement (gt97)
print(f"\nCreating Type A (99% achievement)...")
create_production_record(token, {
    "date": test_date,
    "lane": items[0]["lane"],
    "type": items[0]["type"],
    "ics_no": items[0]["ics_no"],
    "shift": "SHIFT 3",
    "plan_injection": 1000,
    "act_injection": 990,
    "plan_eva": 0,
    "act_eva": 0,
    "plan_assy": 0,
    "act_assy": 0,
    "tt": 20
})

# Type B: ~93% achievement (mid: 90-97)
print(f"Creating Type B (93% achievement)...")
create_production_record(token, {
    "date": test_date,
    "lane": items[1]["lane"],
    "type": items[1]["type"],
    "ics_no": items[1]["ics_no"],
    "shift": "SHIFT 3",
    "plan_injection": 1000,
    "act_injection": 930,
    "plan_eva": 0,
    "act_eva": 0,
    "plan_assy": 0,
    "act_assy": 0,
    "tt": 20
})

# Type C: ~85% achievement (lt90)
print(f"Creating Type C (85% achievement)...")
create_production_record(token, {
    "date": test_date,
    "lane": items[2]["lane"],
    "type": items[2]["type"],
    "ics_no": items[2]["ics_no"],
    "shift": "SHIFT 3",
    "plan_injection": 1000,
    "act_injection": 850,
    "plan_eva": 0,
    "act_eva": 0,
    "plan_assy": 0,
    "act_assy": 0,
    "tt": 20
})

print(f"\nCreated {len(created_ids)} records")

# Get production records
resp = requests.get(f"{BASE_URL}/smt-production?date_from={test_date}&date_to={test_date}", headers=headers)
records = resp.json()

print(f"\nProduction records for {test_date}: {len(records)} records")

# Group by type
type_agg = {}
for x in records:
    typ = x.get("type", "-")
    if typ not in type_agg:
        type_agg[typ] = {"plan": 0.0, "act": 0.0, "records": []}
    type_agg[typ]["plan"] += x.get("plan_part", 0)
    type_agg[typ]["act"] += x.get("total_act_part", 0)
    type_agg[typ]["records"].append(x)

print("\nType aggregation:")
for typ, a in type_agg.items():
    if a["plan"] > 0:
        ach = a["act"] / a["plan"] * 100
        bucket = "gt97" if ach > 97 else ("mid" if ach >= 90 else "lt90")
        print(f"  Type {typ}: plan={a['plan']}, act={a['act']}, ach={ach:.1f}% → {bucket}")
        print(f"    Records: {len(a['records'])}")

# Get dashboard
resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}", headers=headers)
data = resp.json()

print("\nDashboard achievement data:")
achievement = data.get("resume", {}).get("achievement", {})
print(f"  gt97: total_plan={achievement.get('gt97', {}).get('total_plan')}, act={achievement.get('gt97', {}).get('act')}, avg={achievement.get('gt97', {}).get('average')}")
print(f"  mid:  total_plan={achievement.get('mid', {}).get('total_plan')}, act={achievement.get('mid', {}).get('act')}, avg={achievement.get('mid', {}).get('average')}")
print(f"  lt90: total_plan={achievement.get('lt90', {}).get('total_plan')}, act={achievement.get('lt90', {}).get('act')}, avg={achievement.get('lt90', {}).get('average')}")

# Cleanup
print(f"\nCleaning up {len(created_ids)} records...")
for record_id in created_ids:
    requests.delete(f"{BASE_URL}/smt-production/{record_id}", headers=headers)
print("Done")
