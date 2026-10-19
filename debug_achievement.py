#!/usr/bin/env python3
"""Debug achievement categories test"""

import requests

BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    return resp.json()["token"]

def get_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

token = login()
headers = get_headers(token)

# Get dashboard for the achievement test date
test_date = "2026-01-16"
resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}", headers=headers)
data = resp.json()

print("Achievement data:")
achievement = data.get("resume", {}).get("achievement", {})
print(f"gt97: {achievement.get('gt97')}")
print(f"mid: {achievement.get('mid')}")
print(f"lt90: {achievement.get('lt90')}")

# Get production records for this date
resp = requests.get(f"{BASE_URL}/smt-production?date_from={test_date}&date_to={test_date}", headers=headers)
records = resp.json()

print(f"\nProduction records for {test_date}: {len(records)} records")

# Group by type and calculate achievement
type_agg = {}
for x in records:
    typ = x.get("type", "-")
    if typ not in type_agg:
        type_agg[typ] = {"plan": 0.0, "act": 0.0}
    type_agg[typ]["plan"] += x.get("plan_part", 0)
    type_agg[typ]["act"] += x.get("total_act_part", 0)

print("\nType aggregation:")
for typ, a in type_agg.items():
    if a["plan"] > 0:
        ach = a["act"] / a["plan"] * 100
        bucket = "gt97" if ach > 97 else ("mid" if ach >= 90 else "lt90")
        print(f"  Type {typ}: plan={a['plan']}, act={a['act']}, ach={ach:.1f}% → {bucket}")
