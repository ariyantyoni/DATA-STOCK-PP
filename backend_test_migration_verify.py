#!/usr/bin/env python3
"""
Re-verification test for Master Item data migration.
Verifies that led_rank field has been removed and proses_mesin field exists on all 119 items.
"""

import requests
import os

# Backend URL from environment
BACKEND_URL = "https://data-stock-branch.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def login():
    """Login and get auth token"""
    print("=" * 80)
    print("TEST: Authentication")
    print("=" * 80)
    
    url = f"{BACKEND_URL}/auth/login"
    payload = {
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    }
    
    print(f"POST {url}")
    print(f"Payload: {payload}")
    
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        return None
    
    data = response.json()
    token = data.get("token")
    print(f"✅ Login successful. Token: {token[:20]}...")
    return token

def verify_master_items_migration(token):
    """
    Verify the data migration on master items:
    1. NO items should contain 'led_rank' field
    2. ALL items should contain 'proses_mesin' field
    3. Total count should be 119
    4. List endpoint should return without errors
    """
    print("\n" + "=" * 80)
    print("TEST: Master Items Migration Verification")
    print("=" * 80)
    
    url = f"{BACKEND_URL}/items"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAIL: List endpoint returned error: {response.text}")
        return {
            "success": False,
            "error": f"API returned {response.status_code}",
            "total_count": 0,
            "items_with_led_rank": 0,
            "items_with_proses_mesin": 0
        }
    
    print("✅ List endpoint returned successfully")
    
    items = response.json()
    total_count = len(items)
    
    print(f"\nTotal items returned: {total_count}")
    
    # Check each item for led_rank and proses_mesin
    items_with_led_rank = []
    items_without_proses_mesin = []
    
    for item in items:
        item_id = item.get("id", "unknown")
        product = item.get("product", "unknown")
        
        # Check for led_rank (should NOT exist)
        if "led_rank" in item:
            items_with_led_rank.append({
                "id": item_id,
                "product": product,
                "led_rank": item["led_rank"]
            })
        
        # Check for proses_mesin (should exist)
        if "proses_mesin" not in item:
            items_without_proses_mesin.append({
                "id": item_id,
                "product": product
            })
    
    # Print results
    print("\n" + "-" * 80)
    print("VERIFICATION RESULTS:")
    print("-" * 80)
    
    print(f"\n1. Total item count: {total_count}")
    if total_count == 119:
        print("   ✅ PASS: Count is exactly 119")
    else:
        print(f"   ❌ FAIL: Expected 119, got {total_count}")
    
    print(f"\n2. Items containing 'led_rank' field: {len(items_with_led_rank)}")
    if len(items_with_led_rank) == 0:
        print("   ✅ PASS: NO items contain led_rank field")
    else:
        print(f"   ❌ FAIL: {len(items_with_led_rank)} items still contain led_rank field")
        print("   First 5 items with led_rank:")
        for item in items_with_led_rank[:5]:
            print(f"      - ID: {item['id']}, Product: {item['product']}, led_rank: {item['led_rank']}")
        if len(items_with_led_rank) > 5:
            print(f"      ... and {len(items_with_led_rank) - 5} more")
    
    print(f"\n3. Items containing 'proses_mesin' field: {total_count - len(items_without_proses_mesin)}")
    if len(items_without_proses_mesin) == 0:
        print("   ✅ PASS: ALL items contain proses_mesin field")
    else:
        print(f"   ❌ FAIL: {len(items_without_proses_mesin)} items missing proses_mesin field")
        print("   First 5 items without proses_mesin:")
        for item in items_without_proses_mesin[:5]:
            print(f"      - ID: {item['id']}, Product: {item['product']}")
        if len(items_without_proses_mesin) > 5:
            print(f"      ... and {len(items_without_proses_mesin) - 5} more")
    
    # Sample a few items to show their structure
    print("\n4. Sample items (first 3):")
    for i, item in enumerate(items[:3]):
        print(f"\n   Item {i+1}:")
        print(f"      ID: {item.get('id', 'N/A')}")
        print(f"      Product: {item.get('product', 'N/A')}")
        print(f"      Has led_rank: {'led_rank' in item}")
        print(f"      Has proses_mesin: {'proses_mesin' in item}")
        if 'proses_mesin' in item:
            print(f"      proses_mesin value: '{item['proses_mesin']}'")
        if 'led_rank' in item:
            print(f"      led_rank value: '{item['led_rank']}'")
    
    # Final verdict
    print("\n" + "=" * 80)
    print("FINAL VERDICT:")
    print("=" * 80)
    
    all_pass = (
        total_count == 119 and
        len(items_with_led_rank) == 0 and
        len(items_without_proses_mesin) == 0
    )
    
    if all_pass:
        print("✅ PASS: Migration successful!")
        print("   - Total count: 119 ✓")
        print("   - Items with led_rank: 0 ✓")
        print("   - Items with proses_mesin: 119 ✓")
    else:
        print("❌ FAIL: Migration incomplete or failed")
        print(f"   - Total count: {total_count} {'✓' if total_count == 119 else '✗'}")
        print(f"   - Items with led_rank: {len(items_with_led_rank)} {'✓' if len(items_with_led_rank) == 0 else '✗'}")
        print(f"   - Items with proses_mesin: {total_count - len(items_without_proses_mesin)} {'✓' if len(items_without_proses_mesin) == 0 else '✗'}")
    
    return {
        "success": all_pass,
        "total_count": total_count,
        "items_with_led_rank": len(items_with_led_rank),
        "items_with_proses_mesin": total_count - len(items_without_proses_mesin),
        "items_with_led_rank_list": items_with_led_rank,
        "items_without_proses_mesin_list": items_without_proses_mesin
    }

def main():
    print("MASTER ITEM DATA MIGRATION RE-VERIFICATION TEST")
    print("=" * 80)
    print("Purpose: Verify that led_rank field has been removed and proses_mesin")
    print("         field has been added to all 119 master items.")
    print("=" * 80)
    
    # Step 1: Login
    token = login()
    if not token:
        print("\n❌ TEST ABORTED: Authentication failed")
        return
    
    # Step 2: Verify migration
    result = verify_master_items_migration(token)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    if result["success"]:
        print("✅ ALL CHECKS PASSED")
        print(f"   Total items: {result['total_count']}")
        print(f"   Items with led_rank: {result['items_with_led_rank']}")
        print(f"   Items with proses_mesin: {result['items_with_proses_mesin']}")
    else:
        print("❌ SOME CHECKS FAILED")
        print(f"   Total items: {result['total_count']} (expected: 119)")
        print(f"   Items with led_rank: {result['items_with_led_rank']} (expected: 0)")
        print(f"   Items with proses_mesin: {result['items_with_proses_mesin']} (expected: 119)")

if __name__ == "__main__":
    main()
