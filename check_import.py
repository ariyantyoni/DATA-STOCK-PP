#!/usr/bin/env python3
"""
Check for imported item
"""

import requests

BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Login
response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    timeout=10
)
token = response.json()["token"]

# Get all items
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{BASE_URL}/items", headers=headers, timeout=10)
items = response.json()

print(f"Total items: {len(items)}")

# Look for items with ics_no containing 99999
import_test_items = [item for item in items if "99999" in item.get("ics_no", "")]

if import_test_items:
    print(f"\nFound {len(import_test_items)} items with ics_no containing 99999:")
    for item in import_test_items:
        print(f"\nICS No: {item.get('ics_no')}")
        print(f"Type: {item.get('type')}")
        print(f"proses_mesin: {item.get('proses_mesin')}")
        print(f"led_rank present: {'led_rank' in item}")
        print(f"ID: {item.get('id')}")
else:
    print("\nNo items found with ics_no containing 99999")

# Also check for IMPORT-TEST type
import_test_type = [item for item in items if item.get("type") == "IMPORT-TEST"]
if import_test_type:
    print(f"\nFound {len(import_test_type)} items with type IMPORT-TEST:")
    for item in import_test_type:
        print(f"\nICS No: {item.get('ics_no')}")
        print(f"proses_mesin: {item.get('proses_mesin')}")
        print(f"led_rank present: {'led_rank' in item}")
