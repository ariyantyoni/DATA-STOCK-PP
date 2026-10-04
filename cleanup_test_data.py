#!/usr/bin/env python3
"""
Clean up test data from previous runs
"""

import requests

BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    if response.status_code == 200:
        return response.json()["token"]
    return None

def cleanup_production(token):
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get all production records for date 2026-10-05
    response = requests.get(f"{BASE_URL}/smt-production?date_from=2026-10-05&date_to=2026-10-05", headers=headers)
    if response.status_code != 200:
        print(f"Failed to get production records: {response.status_code}")
        return
    
    records = response.json()
    print(f"Found {len(records)} production records for 2026-10-05")
    
    for record in records:
        record_id = record.get("id") or record.get("_id")
        ics_no = record.get("ics_no")
        item_type = record.get("type")
        shift = record.get("shift", "N/A")
        
        response = requests.delete(f"{BASE_URL}/smt-production/{record_id}", headers=headers)
        if response.status_code == 200:
            print(f"✓ Deleted production record: ics_no={ics_no}, type={item_type}, shift={shift}")
        else:
            print(f"✗ Failed to delete production record {record_id}: {response.status_code}")

def cleanup_stock(token):
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get all stock records for date 2026-10-06
    response = requests.get(f"{BASE_URL}/smt-stock?date_from=2026-10-06&date_to=2026-10-06", headers=headers)
    if response.status_code != 200:
        print(f"Failed to get stock records: {response.status_code}")
        return
    
    records = response.json()
    print(f"Found {len(records)} stock records for 2026-10-06")
    
    for record in records:
        record_id = record.get("id") or record.get("_id")
        ics_no = record.get("ics_no")
        item_type = record.get("type")
        shift = record.get("shift", "N/A")
        
        response = requests.delete(f"{BASE_URL}/smt-stock/{record_id}", headers=headers)
        if response.status_code == 200:
            print(f"✓ Deleted stock record: ics_no={ics_no}, type={item_type}, shift={shift}")
        else:
            print(f"✗ Failed to delete stock record {record_id}: {response.status_code}")

def main():
    print("=== CLEANUP TEST DATA ===")
    token = login()
    if not token:
        print("Login failed")
        return
    
    print("\nCleaning up production records...")
    cleanup_production(token)
    
    print("\nCleaning up stock records...")
    cleanup_stock(token)
    
    print("\nCleanup complete")

if __name__ == "__main__":
    main()
