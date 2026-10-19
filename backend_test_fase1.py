#!/usr/bin/env python3
"""
FASE 1 Master Item Enhancement Testing
Tests new fields: ics_name, group, std_stock_min, std_stock_max
"""

import requests
import json
import csv
import io
from openpyxl import Workbook

# Configuration
BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
USERNAME = "admin"
PASSWORD = "admin123"

# Test tracking
test_results = []
created_items = []  # Track created items for cleanup

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"test": test_name, "passed": passed, "details": details})
    print(f"{status}: {test_name}")
    if details:
        print(f"   {details}")

def login():
    """Authenticate and return session with token"""
    session = requests.Session()
    response = session.post(f"{BASE_URL}/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    if response.status_code == 200:
        print(f"✓ Authenticated as {USERNAME}")
        return session
    else:
        print(f"✗ Authentication failed: {response.status_code} - {response.text}")
        return None

def get_initial_count(session):
    """Get initial item count (should be 618)"""
    response = session.get(f"{BASE_URL}/items")
    if response.status_code == 200:
        count = len(response.json())
        print(f"✓ Initial item count: {count}")
        return count
    else:
        print(f"✗ Failed to get items: {response.status_code}")
        return None

def test_1_create_with_new_fields(session):
    """Test 1: POST /api/items with new fields"""
    print("\n=== TEST 1: Create item with new fields ===")
    
    item_data = {
        "lane": "TEST LANE",
        "product": "REGULER",
        "type": "ZT1",
        "ics_no": "9990001110",
        "ics_name": "CONN A",
        "group": "GROUP 2",
        "std_stock_min": 100,
        "std_stock_max": 500,
        "tt": 20,
        "tt_assy": 10,
        "material_per_unit": 2,
        "proses_mesin": "INJECTION"
    }
    
    response = session.post(f"{BASE_URL}/items", json=item_data)
    
    if response.status_code == 200:
        created = response.json()
        created_items.append(created["id"])
        
        # Verify all fields are present
        checks = [
            ("ics_name", created.get("ics_name") == "CONN A"),
            ("group", created.get("group") == "GROUP 2"),
            ("std_stock_min", created.get("std_stock_min") == 100),
            ("std_stock_max", created.get("std_stock_max") == 500),
            ("cap_h", created.get("cap_h") == 180.0)  # 3600/20
        ]
        
        all_passed = all(check[1] for check in checks)
        details = ", ".join([f"{k}={created.get(k)}" for k, _ in checks])
        log_test("1a. Create item with new fields", all_passed, details)
        
        # Verify via GET
        response_get = session.get(f"{BASE_URL}/items?type=ZT1")
        if response_get.status_code == 200:
            items = response_get.json()
            if len(items) > 0:
                item = items[0]
                get_checks = [
                    item.get("ics_name") == "CONN A",
                    item.get("group") == "GROUP 2",
                    item.get("std_stock_min") == 100,
                    item.get("std_stock_max") == 500,
                    item.get("cap_h") == 180.0
                ]
                log_test("1b. GET item returns new fields", all(get_checks), 
                        f"ics_name={item.get('ics_name')}, group={item.get('group')}, min={item.get('std_stock_min')}, max={item.get('std_stock_max')}")
            else:
                log_test("1b. GET item returns new fields", False, "No items found")
        else:
            log_test("1b. GET item returns new fields", False, f"GET failed: {response_get.status_code}")
    else:
        log_test("1a. Create item with new fields", False, f"HTTP {response.status_code}: {response.text}")

def test_2_validation(session):
    """Test 2: Validation rules"""
    print("\n=== TEST 2: Validation rules ===")
    
    # Test 2a: min > max should return 400
    item_invalid = {
        "lane": "TEST LANE",
        "product": "REGULER",
        "type": "ZT2",
        "ics_no": "9990001111",
        "ics_name": "TEST INVALID",
        "group": "GROUP 1",
        "std_stock_min": 900,
        "std_stock_max": 100,
        "tt": 20
    }
    
    response = session.post(f"{BASE_URL}/items", json=item_invalid)
    passed_2a = response.status_code == 400
    log_test("2a. Validation: min > max returns HTTP 400", passed_2a, 
            f"HTTP {response.status_code}: {response.text[:100] if response.text else ''}")
    
    # Test 2b: Empty std values should be stored as null (not 0)
    item_null = {
        "lane": "TEST LANE",
        "product": "REGULER",
        "type": "ZT3",
        "ics_no": "9990001112",
        "ics_name": "TEST NULL",
        "group": "GROUP 3",
        "std_stock_min": "",
        "std_stock_max": None,
        "tt": 20
    }
    
    response = session.post(f"{BASE_URL}/items", json=item_null)
    if response.status_code == 200:
        created = response.json()
        created_items.append(created["id"])
        
        # Check that values are null, not 0
        is_null_min = created.get("std_stock_min") is None
        is_null_max = created.get("std_stock_max") is None
        passed_2b = is_null_min and is_null_max
        log_test("2b. Validation: empty std values stored as null", passed_2b,
                f"std_stock_min={created.get('std_stock_min')}, std_stock_max={created.get('std_stock_max')}")
    else:
        log_test("2b. Validation: empty std values stored as null", False, 
                f"HTTP {response.status_code}: {response.text}")
    
    # Test 2c: Negative std_stock_min should be clamped to 0
    item_negative = {
        "lane": "TEST LANE",
        "product": "REGULER",
        "type": "ZT4",
        "ics_no": "9990001113",
        "ics_name": "TEST NEGATIVE",
        "group": "GROUP 4",
        "std_stock_min": -5,
        "std_stock_max": 100,
        "tt": 20
    }
    
    response = session.post(f"{BASE_URL}/items", json=item_negative)
    if response.status_code == 200:
        created = response.json()
        created_items.append(created["id"])
        
        passed_2c = created.get("std_stock_min") == 0
        log_test("2c. Validation: negative min clamped to 0", passed_2c,
                f"std_stock_min={created.get('std_stock_min')} (input was -5)")
    else:
        log_test("2c. Validation: negative min clamped to 0", False,
                f"HTTP {response.status_code}: {response.text}")

def test_3_export_template(session):
    """Test 3: Export/template includes new headers"""
    print("\n=== TEST 3: Export/template headers ===")
    
    response = session.get(f"{BASE_URL}/import/items/template")
    
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        
        # Check if it's an Excel file
        if 'spreadsheet' in content_type or 'excel' in content_type:
            # Parse as Excel
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(response.content))
            ws = wb.active
            headers = [cell.value for cell in ws[1]]
        else:
            # Parse as CSV
            try:
                content = response.content.decode('utf-8-sig')
            except UnicodeDecodeError:
                content = response.content.decode('latin-1', errors='ignore')
            
            lines = content.strip().split('\n')
            if lines:
                headers = [h.strip() for h in lines[0].split(',')]
            else:
                headers = []
        
        required_headers = ["ICS NAME", "GROUP", "STD STOCK MIN", "STD STOCK MAX"]
        existing_headers = ["Lane", "Product", "Type", "ICS No.", "T/T (detik)"]
        
        all_required = all(h in headers for h in required_headers)
        all_existing = all(h in headers for h in existing_headers)
        
        log_test("3a. Template includes new headers", all_required,
                f"New headers found: {[h for h in required_headers if h in headers]}")
        log_test("3b. Template includes existing headers", all_existing,
                f"All headers: {headers}")
    else:
        log_test("3a. Template includes new headers", False,
                f"HTTP {response.status_code}: {response.text}")

def test_4_import_csv(session):
    """Test 4: Import CSV with new fields"""
    print("\n=== TEST 4: Import CSV with new fields ===")
    
    # First, get an existing item to update
    response = session.get(f"{BASE_URL}/items")
    if response.status_code != 200:
        log_test("4. Import CSV", False, "Failed to get existing items")
        return
    
    items = response.json()
    if len(items) == 0:
        log_test("4. Import CSV", False, "No existing items found")
        return
    
    existing_item = items[0]
    existing_ics_no = existing_item["ics_no"]
    
    # Create CSV with one UPDATE (existing ics_no) and one INSERT (new ics_no)
    csv_content = """Lane,Product,Type,ICS No.,ICS NAME,GROUP,STD STOCK MIN,STD STOCK MAX,T/T (detik),PROSES MESIN
TEST LANE,REGULER,ZT5,9990001114,NEW ITEM CSV,GROUP 5,200,800,25,VAKUM
{lane},{product},{type},{ics_no},UPDATED ITEM,GROUP 6,150,600,{tt},{proses}""".format(
        lane=existing_item.get("lane", ""),
        product=existing_item.get("product", ""),
        type=existing_item.get("type", ""),
        ics_no=existing_ics_no,
        tt=existing_item.get("tt", 20),
        proses=existing_item.get("proses_mesin", "")
    )
    
    # Preview
    files = {'file': ('test_import.csv', csv_content, 'text/csv')}
    response = session.post(f"{BASE_URL}/import/items/preview", files=files)
    
    if response.status_code == 200:
        preview = response.json()
        has_new = preview.get("new", 0) >= 1
        has_duplicate = preview.get("duplicates", 0) >= 1
        log_test("4a. Import preview: new and duplicate detected", has_new and has_duplicate,
                f"new={preview.get('new')}, duplicates={preview.get('duplicates')}, invalid={preview.get('invalid')}")
    else:
        log_test("4a. Import preview", False, f"HTTP {response.status_code}: {response.text}")
        return
    
    # Confirm import
    files = {'file': ('test_import.csv', csv_content, 'text/csv')}
    response = session.post(f"{BASE_URL}/import/items/confirm", files=files)
    
    if response.status_code == 200:
        result = response.json()
        inserted = result.get("inserted", 0)
        updated = result.get("updated", 0)
        
        passed_4b = inserted >= 1 and updated >= 1
        log_test("4b. Import confirm: inserted and updated", passed_4b,
                f"inserted={inserted}, updated={updated}, skipped={result.get('skipped', 0)}")
        
        # Verify the new item was created with correct fields
        response_get = session.get(f"{BASE_URL}/items?type=ZT5")
        if response_get.status_code == 200:
            items_zt5 = response_get.json()
            if len(items_zt5) > 0:
                new_item = items_zt5[0]
                created_items.append(new_item["id"])
                
                checks = [
                    new_item.get("ics_name") == "NEW ITEM CSV",
                    new_item.get("group") == "GROUP 5",
                    new_item.get("std_stock_min") == 200,
                    new_item.get("std_stock_max") == 800
                ]
                log_test("4c. Imported item has correct new fields", all(checks),
                        f"ics_name={new_item.get('ics_name')}, group={new_item.get('group')}, min={new_item.get('std_stock_min')}, max={new_item.get('std_stock_max')}")
            else:
                log_test("4c. Imported item has correct new fields", False, "Item not found after import")
        
        # Verify the existing item was updated
        response_get = session.get(f"{BASE_URL}/items?ics_no={existing_ics_no}")
        if response_get.status_code == 200:
            items_updated = response_get.json()
            if len(items_updated) > 0:
                updated_item = items_updated[0]
                checks = [
                    updated_item.get("ics_name") == "UPDATED ITEM",
                    updated_item.get("group") == "GROUP 6",
                    updated_item.get("std_stock_min") == 150,
                    updated_item.get("std_stock_max") == 600
                ]
                log_test("4d. Updated item has correct new fields", all(checks),
                        f"ics_name={updated_item.get('ics_name')}, group={updated_item.get('group')}")
                
                # Revert the update to restore original state
                revert_data = {
                    **existing_item,
                    "ics_name": existing_item.get("ics_name", ""),
                    "group": existing_item.get("group", ""),
                    "std_stock_min": existing_item.get("std_stock_min"),
                    "std_stock_max": existing_item.get("std_stock_max")
                }
                session.put(f"{BASE_URL}/items/{updated_item['id']}", json=revert_data)
                print(f"   ℹ Reverted item {existing_ics_no} to original state")
            else:
                log_test("4d. Updated item has correct new fields", False, "Updated item not found")
    else:
        log_test("4b. Import confirm", False, f"HTTP {response.status_code}: {response.text}")

def test_4_import_xlsx(session):
    """Test 4e: Import XLSX with new fields"""
    print("\n=== TEST 4e: Import XLSX ===")
    
    # Create XLSX file
    wb = Workbook()
    ws = wb.active
    ws.append(["Lane", "Product", "Type", "ICS No.", "ICS NAME", "GROUP", "STD STOCK MIN", "STD STOCK MAX", "T/T (detik)", "PROSES MESIN"])
    ws.append(["TEST LANE", "REGULER", "ZT6", "9990001115", "XLSX ITEM", "GROUP 1", 300, 900, 30, "PAINTING"])
    
    # Save to bytes
    xlsx_buffer = io.BytesIO()
    wb.save(xlsx_buffer)
    xlsx_buffer.seek(0)
    
    # Preview
    files = {'file': ('test_import.xlsx', xlsx_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    response = session.post(f"{BASE_URL}/import/items/preview", files=files)
    
    if response.status_code == 200:
        preview = response.json()
        log_test("4e. XLSX preview", preview.get("new", 0) >= 1,
                f"new={preview.get('new')}, invalid={preview.get('invalid')}")
    else:
        log_test("4e. XLSX preview", False, f"HTTP {response.status_code}")
        return
    
    # Confirm
    xlsx_buffer.seek(0)
    files = {'file': ('test_import.xlsx', xlsx_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    response = session.post(f"{BASE_URL}/import/items/confirm", files=files)
    
    if response.status_code == 200:
        result = response.json()
        log_test("4f. XLSX confirm", result.get("inserted", 0) >= 1,
                f"inserted={result.get('inserted')}")
        
        # Verify
        response_get = session.get(f"{BASE_URL}/items?type=ZT6")
        if response_get.status_code == 200:
            items = response_get.json()
            if len(items) > 0:
                item = items[0]
                created_items.append(item["id"])
                checks = [
                    item.get("ics_name") == "XLSX ITEM",
                    item.get("group") == "GROUP 1",
                    item.get("std_stock_min") == 300,
                    item.get("std_stock_max") == 900
                ]
                log_test("4g. XLSX imported item has correct fields", all(checks),
                        f"ics_name={item.get('ics_name')}, group={item.get('group')}")
    else:
        log_test("4f. XLSX confirm", False, f"HTTP {response.status_code}")

def test_4_import_validation(session):
    """Test 4h: Import with min > max should be handled gracefully"""
    print("\n=== TEST 4h: Import validation (min > max) ===")
    
    csv_content = """Lane,Product,Type,ICS No.,ICS NAME,GROUP,STD STOCK MIN,STD STOCK MAX,T/T (detik)
TEST LANE,REGULER,ZT7,9990001116,INVALID MINMAX,GROUP 2,999,100,20"""
    
    files = {'file': ('test_invalid.csv', csv_content, 'text/csv')}
    response = session.post(f"{BASE_URL}/import/items/preview", files=files)
    
    # Should not crash (no 500 error)
    passed = response.status_code in [200, 400]
    log_test("4h. Import with min>max handled gracefully (no 500 crash)", passed,
            f"HTTP {response.status_code}")
    
    if response.status_code == 200:
        preview = response.json()
        # Should be marked as invalid or skipped
        log_test("4i. Invalid row marked appropriately", 
                preview.get("invalid", 0) > 0 or preview.get("skipped", 0) > 0,
                f"invalid={preview.get('invalid')}, skipped={preview.get('skipped')}")

def test_5_meta_options(session):
    """Test 5: meta/options contains groups"""
    print("\n=== TEST 5: meta/options contains groups ===")
    
    response = session.get(f"{BASE_URL}/meta/options")
    
    if response.status_code == 200:
        options = response.json()
        groups = options.get("groups", [])
        
        expected_groups = [f"GROUP {i}" for i in range(1, 7)]
        has_all_groups = all(g in groups for g in expected_groups)
        
        log_test("5a. meta/options contains groups", has_all_groups,
                f"groups={groups}")
        
        # Also verify other options still exist
        has_shifts = "shifts" in options
        has_proses = "proses_mesin" in options
        log_test("5b. meta/options regression (shifts, proses_mesin)", has_shifts and has_proses,
                f"shifts={options.get('shifts')}, proses_mesin count={len(options.get('proses_mesin', []))}")
    else:
        log_test("5a. meta/options contains groups", False,
                f"HTTP {response.status_code}: {response.text}")

def test_6_regression(session, initial_count):
    """Test 6: Regression - items count should be 618 after cleanup"""
    print("\n=== TEST 6: Regression after cleanup ===")
    
    # Clean up all ZT test items
    print(f"\nCleaning up {len(created_items)} test items...")
    deleted_count = 0
    for item_id in created_items:
        response = session.delete(f"{BASE_URL}/items/{item_id}")
        if response.status_code == 200:
            deleted_count += 1
    
    print(f"✓ Deleted {deleted_count} test items")
    
    # Verify count is back to 618
    response = session.get(f"{BASE_URL}/items")
    if response.status_code == 200:
        final_count = len(response.json())
        passed = final_count == initial_count
        log_test("6a. Item count restored to 618", passed,
                f"initial={initial_count}, final={final_count}")
    else:
        log_test("6a. Item count restored to 618", False,
                f"HTTP {response.status_code}")
    
    # Verify meta/options still works
    response = session.get(f"{BASE_URL}/meta/options")
    passed_meta = response.status_code == 200
    log_test("6b. meta/options still working", passed_meta,
            f"HTTP {response.status_code}")
    
    # Verify other list endpoints still work
    endpoints = [
        "/smt-production",
        "/smt-stock",
        "/production-needs",
        "/variance",
        "/stock-standards"
    ]
    
    all_working = True
    for endpoint in endpoints:
        response = session.get(f"{BASE_URL}{endpoint}")
        if response.status_code != 200:
            all_working = False
            print(f"   ✗ {endpoint} returned {response.status_code}")
    
    log_test("6c. Other list endpoints still working", all_working,
            "All endpoints returned 200")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for t in test_results if t["passed"])
    total_count = len(test_results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed\n")
    
    for result in test_results:
        status = "✅" if result["passed"] else "❌"
        print(f"{status} {result['test']}")
        if result["details"] and not result["passed"]:
            print(f"   {result['details']}")
    
    print("\n" + "="*80)
    
    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED")
    else:
        print(f"⚠️  {total_count - passed_count} TEST(S) FAILED")
    
    print("="*80)

def main():
    """Main test execution"""
    print("="*80)
    print("FASE 1 Master Item Enhancement - Backend Testing")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Username: {USERNAME}")
    print("="*80)
    
    # Login
    session = login()
    if not session:
        print("❌ Authentication failed. Exiting.")
        return
    
    # Get initial count
    initial_count = get_initial_count(session)
    if initial_count is None:
        print("❌ Failed to get initial item count. Exiting.")
        return
    
    # Run tests
    try:
        test_1_create_with_new_fields(session)
        test_2_validation(session)
        test_3_export_template(session)
        test_4_import_csv(session)
        test_4_import_xlsx(session)
        test_4_import_validation(session)
        test_5_meta_options(session)
        test_6_regression(session, initial_count)
    except Exception as e:
        print(f"\n❌ Test execution error: {e}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    print_summary()

if __name__ == "__main__":
    main()
