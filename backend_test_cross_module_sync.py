#!/usr/bin/env python3
"""
CROSS-MODULE SYNC VERIFICATION TEST
Re-verify the unique-key fix (shift now in key) and production-needs sync.
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
USERNAME = "admin"
PASSWORD = "admin123"

# Test tracking
created_ids = {"production": [], "stock": []}
test_results = []

def log_test(name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append(f"{status} - {name}")
    if details:
        test_results.append(f"    {details}")
    print(f"{status} - {name}")
    if details:
        print(f"    {details}")

def login():
    """Login and get token"""
    print("\n=== AUTHENTICATION ===")
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    if response.status_code == 200:
        token = response.json()["token"]
        print(f"✓ Logged in as {USERNAME}")
        return token
    else:
        print(f"✗ Login failed: {response.status_code} - {response.text}")
        return None

def get_master_item(token):
    """Get a master item for testing"""
    print("\n=== STEP 1: GET MASTER ITEM ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get items list
    response = requests.get(f"{BASE_URL}/items", headers=headers)
    if response.status_code != 200:
        print(f"✗ Failed to get items: {response.status_code}")
        return None
    
    items = response.json()
    if not items:
        print("✗ No master items found")
        return None
    
    # Pick first item with ics_no 5825091000 type 003 as requested, or fallback to first item
    target_item = None
    for item in items:
        if item.get("ics_no") == "5825091000" and item.get("type") == "003":
            target_item = item
            break
    
    if not target_item:
        target_item = items[0]
    
    print(f"✓ Selected master item: ics_no={target_item['ics_no']}, type={target_item['type']}, product={target_item.get('product', 'N/A')}")
    log_test("Get master item", True, f"ics_no={target_item['ics_no']}, type={target_item['type']}")
    return target_item

def test_unique_key_with_shift(token, master_item):
    """PRIMARY TEST: Create TWO production records with SAME date+ics+type, DIFFERENT shift"""
    print("\n=== PRIMARY TEST: UNIQUE KEY WITH SHIFT ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    test_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    ics_no = master_item["ics_no"]
    item_type = master_item["type"]
    lane = master_item.get("lane", "TEST-LANE")
    
    print(f"Test key: date={test_date}, ics_no={ics_no}, type={item_type}")
    
    # Record A: SHIFT 3, plan_injection=0, plan_eva=50, plan_assy=0
    print("\n--- Creating Record A (SHIFT 3) ---")
    record_a = {
        "date": test_date,
        "lane": lane,
        "ics_no": ics_no,
        "type": item_type,
        "shift": "SHIFT 3",
        "plan_injection": 0,
        "act_injection": 0,
        "plan_eva": 50,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0
    }
    
    response_a = requests.post(f"{BASE_URL}/smt-production", json=record_a, headers=headers)
    print(f"Response A: {response_a.status_code}")
    
    if response_a.status_code == 200:
        data_a = response_a.json()
        record_id = data_a.get("id") or data_a.get("_id")
        created_ids["production"].append(record_id)
        log_test("Create Record A (SHIFT 3)", True, f"HTTP {response_a.status_code} - plan_eva=50")
    else:
        log_test("Create Record A (SHIFT 3)", False, f"HTTP {response_a.status_code} - {response_a.text[:200]}")
        return False
    
    # Record B: SHIFT 1, plan_injection=60
    print("\n--- Creating Record B (SHIFT 1) ---")
    record_b = {
        "date": test_date,
        "lane": lane,
        "ics_no": ics_no,
        "type": item_type,
        "shift": "SHIFT 1",
        "plan_injection": 60,
        "act_injection": 0,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0
    }
    
    response_b = requests.post(f"{BASE_URL}/smt-production", json=record_b, headers=headers)
    print(f"Response B: {response_b.status_code}")
    
    if response_b.status_code == 200:
        data_b = response_b.json()
        record_id = data_b.get("id") or data_b.get("_id")
        created_ids["production"].append(record_id)
        log_test("Create Record B (SHIFT 1)", True, f"HTTP {response_b.status_code} - plan_injection=60")
    elif response_b.status_code == 409:
        log_test("Create Record B (SHIFT 1)", False, f"HTTP 409 DUPLICATE - Unique key bug NOT fixed! Still blocking same date+ics+type")
        return False
    else:
        log_test("Create Record B (SHIFT 1)", False, f"HTTP {response_b.status_code} - {response_b.text[:200]}")
        return False
    
    # Verify both records exist
    print("\n--- Verifying both records persist ---")
    response = requests.get(f"{BASE_URL}/smt-production?date_from={test_date}&date_to={test_date}&ics_no={ics_no}&type={item_type}", headers=headers)
    
    if response.status_code == 200:
        records = response.json()
        count = len(records)
        print(f"Found {count} records for key (date={test_date}, ics_no={ics_no}, type={item_type})")
        
        if count == 2:
            shifts = [r.get("shift") for r in records]
            print(f"Shifts: {shifts}")
            log_test("Both records persist", True, f"Count=2, shifts={shifts}")
            return True
        else:
            log_test("Both records persist", False, f"Expected 2 records, found {count}")
            return False
    else:
        log_test("Both records persist", False, f"HTTP {response.status_code}")
        return False

def test_production_needs_sync(token, master_item):
    """Test production-needs shift indicators"""
    print("\n=== TEST: PRODUCTION-NEEDS SYNC ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    test_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    ics_no = master_item["ics_no"]
    item_type = master_item["type"]
    
    # Get production-needs for this key
    print(f"\n--- Getting production-needs for date={test_date}, ics_no={ics_no}, type={item_type} ---")
    response = requests.get(f"{BASE_URL}/production-needs?date_from={test_date}&date_to={test_date}&ics_no={ics_no}&type={item_type}", headers=headers)
    
    if response.status_code != 200:
        log_test("Get production-needs", False, f"HTTP {response.status_code}")
        return False
    
    needs = response.json()
    if not needs:
        log_test("Get production-needs", False, "No records found")
        return False
    
    need = needs[0]
    print(f"Production needs: shift3={need.get('shift3')}, shift1={need.get('shift1')}, shift2={need.get('shift2')}, kondisi_produksi={need.get('kondisi_produksi')}")
    
    # Expected: shift3=ON (plan_eva=50), shift1=ON (plan_injection=60), shift2=OFF
    expected_shift3 = "ON"
    expected_shift1 = "ON"
    expected_shift2 = "OFF"
    expected_kondisi = "ON"
    
    actual_shift3 = need.get("shift3")
    actual_shift1 = need.get("shift1")
    actual_shift2 = need.get("shift2")
    actual_kondisi = need.get("kondisi_produksi")
    
    all_correct = (
        actual_shift3 == expected_shift3 and
        actual_shift1 == expected_shift1 and
        actual_shift2 == expected_shift2 and
        actual_kondisi == expected_kondisi
    )
    
    if all_correct:
        log_test("Production-needs shift indicators", True, f"shift3={actual_shift3}, shift1={actual_shift1}, shift2={actual_shift2}, kondisi={actual_kondisi}")
    else:
        log_test("Production-needs shift indicators", False, 
                f"Expected: shift3={expected_shift3}, shift1={expected_shift1}, shift2={expected_shift2}, kondisi={expected_kondisi}. "
                f"Actual: shift3={actual_shift3}, shift1={actual_shift1}, shift2={actual_shift2}, kondisi={actual_kondisi}")
    
    return all_correct

def test_live_sync(token, master_item):
    """Test live sync: update production plans and verify production-needs changes"""
    print("\n=== TEST: LIVE SYNC ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    test_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    ics_no = master_item["ics_no"]
    item_type = master_item["type"]
    
    # Get the two production records we created
    response = requests.get(f"{BASE_URL}/smt-production?date_from={test_date}&date_to={test_date}&ics_no={ics_no}&type={item_type}", headers=headers)
    if response.status_code != 200:
        log_test("Get production records for live sync", False, f"HTTP {response.status_code}")
        return False
    
    records = response.json()
    if len(records) != 2:
        log_test("Get production records for live sync", False, f"Expected 2 records, found {len(records)}")
        return False
    
    # Find Record A (SHIFT 3) and Record B (SHIFT 1)
    record_a = next((r for r in records if r.get("shift") == "SHIFT 3"), None)
    record_b = next((r for r in records if r.get("shift") == "SHIFT 1"), None)
    
    if not record_a or not record_b:
        log_test("Find SHIFT 3 and SHIFT 1 records", False, "Records not found")
        return False
    
    # Update Record A: set plan_eva=0 (should flip shift3 to OFF)
    print("\n--- Update Record A: plan_eva=50 → 0 ---")
    record_a["plan_eva"] = 0
    record_a_id = record_a.get("id") or record_a.get("_id")
    response = requests.put(f"{BASE_URL}/smt-production/{record_a_id}", json=record_a, headers=headers)
    
    if response.status_code != 200:
        log_test("Update Record A (plan_eva=0)", False, f"HTTP {response.status_code}")
        return False
    
    print("✓ Record A updated")
    
    # Re-get production-needs, shift3 should be OFF now
    response = requests.get(f"{BASE_URL}/production-needs?date_from={test_date}&date_to={test_date}&ics_no={ics_no}&type={item_type}", headers=headers)
    if response.status_code != 200:
        log_test("Get production-needs after update A", False, f"HTTP {response.status_code}")
        return False
    
    needs = response.json()
    if not needs:
        log_test("Get production-needs after update A", False, "No records found")
        return False
    
    need = needs[0]
    actual_shift3 = need.get("shift3")
    print(f"After update A: shift3={actual_shift3} (expected: OFF)")
    
    if actual_shift3 != "OFF":
        log_test("Live sync: shift3 flips to OFF", False, f"Expected OFF, got {actual_shift3}")
        return False
    
    log_test("Live sync: shift3 flips to OFF", True, f"shift3={actual_shift3}")
    
    # Update Record B: set plan_injection=0 (should flip shift1 to OFF, kondisi_produksi to OFF)
    print("\n--- Update Record B: plan_injection=60 → 0 ---")
    record_b["plan_injection"] = 0
    record_b_id = record_b.get("id") or record_b.get("_id")
    response = requests.put(f"{BASE_URL}/smt-production/{record_b_id}", json=record_b, headers=headers)
    
    if response.status_code != 200:
        log_test("Update Record B (plan_injection=0)", False, f"HTTP {response.status_code}")
        return False
    
    print("✓ Record B updated")
    
    # Re-get production-needs, shift1 and kondisi_produksi should be OFF now
    response = requests.get(f"{BASE_URL}/production-needs?date_from={test_date}&date_to={test_date}&ics_no={ics_no}&type={item_type}", headers=headers)
    if response.status_code != 200:
        log_test("Get production-needs after update B", False, f"HTTP {response.status_code}")
        return False
    
    needs = response.json()
    if not needs:
        log_test("Get production-needs after update B", False, "No records found")
        return False
    
    need = needs[0]
    actual_shift1 = need.get("shift1")
    actual_kondisi = need.get("kondisi_produksi")
    print(f"After update B: shift1={actual_shift1} (expected: OFF), kondisi_produksi={actual_kondisi} (expected: OFF)")
    
    if actual_shift1 != "OFF":
        log_test("Live sync: shift1 flips to OFF", False, f"Expected OFF, got {actual_shift1}")
        return False
    
    log_test("Live sync: shift1 flips to OFF", True, f"shift1={actual_shift1}")
    
    if actual_kondisi != "OFF":
        log_test("Live sync: kondisi_produksi flips to OFF", False, f"Expected OFF, got {actual_kondisi}")
        return False
    
    log_test("Live sync: kondisi_produksi flips to OFF", True, f"kondisi_produksi={actual_kondisi}")
    
    return True

def test_shift2_record(token, master_item):
    """Create SHIFT 2 record and verify shift2 becomes ON"""
    print("\n=== TEST: CREATE SHIFT 2 RECORD ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    test_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    ics_no = master_item["ics_no"]
    item_type = master_item["type"]
    lane = master_item.get("lane", "TEST-LANE")
    
    # Create SHIFT 2 record with plan_injection=5
    print(f"\n--- Creating SHIFT 2 record with plan_injection=5 ---")
    record_c = {
        "date": test_date,
        "lane": lane,
        "ics_no": ics_no,
        "type": item_type,
        "shift": "SHIFT 2",
        "plan_injection": 5,
        "act_injection": 0,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0
    }
    
    response = requests.post(f"{BASE_URL}/smt-production", json=record_c, headers=headers)
    print(f"Response: {response.status_code}")
    
    if response.status_code == 200:
        data_c = response.json()
        record_id = data_c.get("id") or data_c.get("_id")
        created_ids["production"].append(record_id)
        log_test("Create SHIFT 2 record", True, f"HTTP {response.status_code}")
    else:
        log_test("Create SHIFT 2 record", False, f"HTTP {response.status_code} - {response.text[:200]}")
        return False
    
    # Get production-needs, shift2 should be ON now
    response = requests.get(f"{BASE_URL}/production-needs?date_from={test_date}&date_to={test_date}&ics_no={ics_no}&type={item_type}", headers=headers)
    if response.status_code != 200:
        log_test("Get production-needs after SHIFT 2", False, f"HTTP {response.status_code}")
        return False
    
    needs = response.json()
    if not needs:
        log_test("Get production-needs after SHIFT 2", False, "No records found")
        return False
    
    need = needs[0]
    actual_shift2 = need.get("shift2")
    print(f"After SHIFT 2 creation: shift2={actual_shift2} (expected: ON)")
    
    if actual_shift2 != "ON":
        log_test("shift2 becomes ON", False, f"Expected ON, got {actual_shift2}")
        return False
    
    log_test("shift2 becomes ON", True, f"shift2={actual_shift2}")
    return True

def test_stock_regression(token, master_item):
    """SECONDARY: Quick regression on smt-stock"""
    print("\n=== SECONDARY TEST: SMT-STOCK REGRESSION ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    test_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    ics_no = master_item["ics_no"]
    item_type = master_item["type"]
    lane = master_item.get("lane", "TEST-LANE")
    
    # Create two stock records with different shifts, same date+ics+type
    print("\n--- Creating stock record SHIFT 3 ---")
    stock_a = {
        "date": test_date,
        "lane": lane,
        "ics_no": ics_no,
        "type": item_type,
        "shift": "SHIFT 3",
        "group1": 10,
        "group2": 20,
        "group3": 30,
        "group4": 40,
        "group5": 50,
        "group6": 60,
        "part_ragu": 5
    }
    
    response_a = requests.post(f"{BASE_URL}/smt-stock", json=stock_a, headers=headers)
    if response_a.status_code == 200:
        data_a = response_a.json()
        record_id = data_a.get("id") or data_a.get("_id")
        created_ids["stock"].append(record_id)
        log_test("Create stock SHIFT 3", True, f"HTTP {response_a.status_code}")
    else:
        log_test("Create stock SHIFT 3", False, f"HTTP {response_a.status_code}")
        return False
    
    print("\n--- Creating stock record SHIFT 1 ---")
    stock_b = {
        "date": test_date,
        "lane": lane,
        "ics_no": ics_no,
        "type": item_type,
        "shift": "SHIFT 1",
        "group1": 15,
        "group2": 25,
        "group3": 35,
        "group4": 45,
        "group5": 55,
        "group6": 65,
        "part_ragu": 10
    }
    
    response_b = requests.post(f"{BASE_URL}/smt-stock", json=stock_b, headers=headers)
    if response_b.status_code == 200:
        data_b = response_b.json()
        record_id = data_b.get("id") or data_b.get("_id")
        created_ids["stock"].append(record_id)
        log_test("Create stock SHIFT 1", True, f"HTTP {response_b.status_code}")
    elif response_b.status_code == 409:
        log_test("Create stock SHIFT 1", False, "HTTP 409 DUPLICATE - shift not in key for smt-stock")
        return False
    else:
        log_test("Create stock SHIFT 1", False, f"HTTP {response_b.status_code}")
        return False
    
    # Verify total computation
    stock_a_data = response_a.json()
    expected_total_a = 10 + 20 + 30 + 40 + 50 + 60 + 5  # 215
    actual_total_a = stock_a_data.get("total")
    
    if actual_total_a == expected_total_a:
        log_test("Stock total computation", True, f"total={actual_total_a}")
    else:
        log_test("Stock total computation", False, f"Expected {expected_total_a}, got {actual_total_a}")
        return False
    
    # Test shift filter
    response = requests.get(f"{BASE_URL}/smt-stock?shift=SHIFT 3", headers=headers)
    if response.status_code == 200:
        records = [r for r in response.json() if r.get("shift") == "SHIFT 3"]
        if len(records) > 0:
            log_test("Stock shift filter", True, f"Found {len(records)} SHIFT 3 records")
        else:
            log_test("Stock shift filter", False, "No SHIFT 3 records found")
            return False
    else:
        log_test("Stock shift filter", False, f"HTTP {response.status_code}")
        return False
    
    # Test proses_mesin filter
    proses_mesin = master_item.get("proses_mesin", "")
    if proses_mesin:
        response = requests.get(f"{BASE_URL}/smt-stock?proses_mesin={proses_mesin}", headers=headers)
        if response.status_code == 200:
            log_test("Stock proses_mesin filter", True, f"HTTP {response.status_code}")
        else:
            log_test("Stock proses_mesin filter", False, f"HTTP {response.status_code}")
            return False
    
    return True

def test_production_regression(token):
    """SECONDARY: Quick regression on smt-production compute"""
    print("\n=== SECONDARY TEST: SMT-PRODUCTION COMPUTE ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get one of the production records we created
    if not created_ids["production"]:
        log_test("Production compute regression", False, "No production records to test")
        return False
    
    prod_id = created_ids["production"][0]
    response = requests.get(f"{BASE_URL}/smt-production", headers=headers)
    
    if response.status_code != 200:
        log_test("Production compute regression", False, f"HTTP {response.status_code}")
        return False
    
    records = response.json()
    record = next((r for r in records if r.get("id") == prod_id or r.get("_id") == prod_id), None)
    
    if not record:
        log_test("Production compute regression", False, "Record not found")
        return False
    
    # Verify computed fields exist
    required_fields = ["total_act", "total_plan", "total_act_part", "total_act_assy", "plan_part", "achv", "balance"]
    missing_fields = [f for f in required_fields if f not in record]
    
    if missing_fields:
        log_test("Production compute regression", False, f"Missing fields: {missing_fields}")
        return False
    
    log_test("Production compute regression", True, f"All computed fields present")
    
    # Test shift filter
    response = requests.get(f"{BASE_URL}/smt-production?shift=SHIFT 3", headers=headers)
    if response.status_code == 200:
        log_test("Production shift filter", True, f"HTTP {response.status_code}")
    else:
        log_test("Production shift filter", False, f"HTTP {response.status_code}")
        return False
    
    return True

def test_other_modules(token):
    """SECONDARY: Quick check on variance, dashboard, meta"""
    print("\n=== SECONDARY TEST: OTHER MODULES ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Variance
    response = requests.get(f"{BASE_URL}/variance", headers=headers)
    if response.status_code == 200:
        log_test("Variance endpoint", True, f"HTTP {response.status_code}")
    else:
        log_test("Variance endpoint", False, f"HTTP {response.status_code}")
        return False
    
    # Dashboard
    response = requests.get(f"{BASE_URL}/dashboard/summary", headers=headers)
    if response.status_code == 200:
        log_test("Dashboard endpoint", True, f"HTTP {response.status_code}")
    else:
        log_test("Dashboard endpoint", False, f"HTTP {response.status_code}")
        return False
    
    # Meta options
    response = requests.get(f"{BASE_URL}/meta/options", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if "shifts" in data and "proses_mesin" in data:
            log_test("Meta options", True, f"shifts and proses_mesin present")
        else:
            log_test("Meta options", False, "Missing shifts or proses_mesin")
            return False
    else:
        log_test("Meta options", False, f"HTTP {response.status_code}")
        return False
    
    return True

def test_master_item_count(token):
    """SECONDARY: Verify master item count is still 618"""
    print("\n=== SECONDARY TEST: MASTER ITEM COUNT ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{BASE_URL}/items", headers=headers)
    if response.status_code != 200:
        log_test("Master item count", False, f"HTTP {response.status_code}")
        return False
    
    items = response.json()
    count = len(items)
    
    if count == 618:
        log_test("Master item count", True, f"Count={count}")
        return True
    else:
        log_test("Master item count", False, f"Expected 618, got {count}")
        return False

def cleanup(token):
    """Clean up all created test data"""
    print("\n=== CLEANUP ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Delete production records
    for prod_id in created_ids["production"]:
        response = requests.delete(f"{BASE_URL}/smt-production/{prod_id}", headers=headers)
        if response.status_code == 200:
            print(f"✓ Deleted production record {prod_id}")
        else:
            print(f"✗ Failed to delete production record {prod_id}: {response.status_code}")
    
    # Delete stock records
    for stock_id in created_ids["stock"]:
        response = requests.delete(f"{BASE_URL}/smt-stock/{stock_id}", headers=headers)
        if response.status_code == 200:
            print(f"✓ Deleted stock record {stock_id}")
        else:
            print(f"✗ Failed to delete stock record {stock_id}: {response.status_code}")
    
    print(f"\nCleanup complete: {len(created_ids['production'])} production + {len(created_ids['stock'])} stock records deleted")
    log_test("Cleanup", True, f"{len(created_ids['production'])} production + {len(created_ids['stock'])} stock records deleted")

def verify_cleanup(token):
    """Verify master item count is still 618 after cleanup"""
    print("\n=== VERIFY CLEANUP ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{BASE_URL}/items", headers=headers)
    if response.status_code != 200:
        log_test("Verify cleanup - item count", False, f"HTTP {response.status_code}")
        return False
    
    items = response.json()
    count = len(items)
    
    if count == 618:
        log_test("Verify cleanup - item count", True, f"Count={count} (unchanged)")
        return True
    else:
        log_test("Verify cleanup - item count", False, f"Expected 618, got {count}")
        return False

def main():
    """Main test execution"""
    print("=" * 80)
    print("CROSS-MODULE SYNC VERIFICATION TEST")
    print("Testing unique-key fix (shift in key) and production-needs sync")
    print("=" * 80)
    
    # Login
    token = login()
    if not token:
        print("\n❌ AUTHENTICATION FAILED - Cannot proceed")
        return
    
    # Get master item
    master_item = get_master_item(token)
    if not master_item:
        print("\n❌ NO MASTER ITEM - Cannot proceed")
        return
    
    # PRIMARY TESTS
    print("\n" + "=" * 80)
    print("PRIMARY TESTS: CROSS-MODULE SYNC")
    print("=" * 80)
    
    test_unique_key_with_shift(token, master_item)
    test_production_needs_sync(token, master_item)
    test_live_sync(token, master_item)
    test_shift2_record(token, master_item)
    
    # SECONDARY TESTS
    print("\n" + "=" * 80)
    print("SECONDARY TESTS: REGRESSION")
    print("=" * 80)
    
    test_stock_regression(token, master_item)
    test_production_regression(token)
    test_other_modules(token)
    test_master_item_count(token)
    
    # CLEANUP
    cleanup(token)
    verify_cleanup(token)
    
    # SUMMARY
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for result in test_results:
        print(result)
    
    passed = sum(1 for r in test_results if "✅ PASS" in r)
    failed = sum(1 for r in test_results if "❌ FAIL" in r)
    total = passed + failed
    
    print(f"\nTotal: {total} tests, {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED")
    else:
        print(f"\n⚠️ {failed} TEST(S) FAILED")

if __name__ == "__main__":
    main()
