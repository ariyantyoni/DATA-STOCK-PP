#!/usr/bin/env python3
"""
Quick check: Verify what fields are actually returned by the API
"""

import requests
import json

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

# Get items
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{BASE_URL}/items", headers=headers, timeout=10)
items = response.json()

print(f"Total items: {len(items)}")
print("\nFirst item fields:")
if items:
    first_item = items[0]
    print(json.dumps(first_item, indent=2))
    
    # Check for led_rank
    has_led_rank = "led_rank" in first_item
    has_proses_mesin = "proses_mesin" in first_item
    
    print(f"\nHas led_rank: {has_led_rank}")
    print(f"Has proses_mesin: {has_proses_mesin}")
    
    # Count items with each field
    items_with_led_rank = sum(1 for item in items if "led_rank" in item)
    items_with_proses_mesin = sum(1 for item in items if "proses_mesin" in item)
    
    print(f"\nItems with led_rank: {items_with_led_rank}/{len(items)}")
    print(f"Items with proses_mesin: {items_with_proses_mesin}/{len(items)}")
