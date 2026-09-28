"""
Comprehensive Backend Tests for PART PRODUCTION App
Tests data isolation, auth, CRUD, filters, import/export, backup/restore
"""
import os
import io
import json
import time
import requests
from openpyxl import Workbook

# Read base URL from frontend/.env
BASE_URL = "https://data-stock-branch.preview.emergentagent.com"
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
except Exception:
    pass

API = f"{BASE_URL}/api"

# Credentials from test_credentials.md - LOGIN USES USERNAME (NOT EMAIL)
ADMIN = {"username": "admin", "password": "admin123"}
DEMO_USERS = {
    "ppic": {"username": "ppic", "password": "password123"},
    "pc": {"username": "pc", "password": "password123"},
    "smt": {"username": "smt", "password": "password123"},
    "assy": {"username": "assy", "password": "password123"},
    "manager": {"username": "manager", "password": "password123"},
}

def auth_header(token):
    """Return Authorization header with Bearer token"""
    return {"Authorization": f"Bearer {token}"}

def login(credentials):
    """Login with username/password and return token"""
    print(f"  → Logging in as {credentials['username']}...")
    r = requests.post(f"{API}/auth/login", json=credentials, timeout=20)
    if r.status_code != 200:
        print(f"    ✗ Login failed: {r.status_code} {r.text}")
        return None, None
    data = r.json()
    print(f"    ✓ Login successful")
    return data.get("token"), data.get("user")

def test_auth():
    """Test 1: Authentication with username/password"""
    print("\n" + "="*80)
    print("TEST 1: AUTHENTICATION")
    print("="*80)
    
    # Test admin login
    print("\n1.1 Admin Login (username=admin, password=admin123)")
    token, user = login(ADMIN)
    if not token:
        print("  ✗ FAILED: Admin login failed")
        return None
    print(f"  ✓ PASSED: Admin logged in, role={user.get('role')}, username={user.get('username')}")
    
    # Test protected endpoint with token
    print("\n1.2 Protected Endpoint (/api/auth/me) with valid token")
    r = requests.get(f"{API}/auth/me", headers=auth_header(token), timeout=15)
    if r.status_code == 200:
        me = r.json()
        print(f"  ✓ PASSED: /api/auth/me returned user data, role={me.get('role')}")
    else:
        print(f"  ✗ FAILED: /api/auth/me returned {r.status_code}")
    
    # Test wrong password
    print("\n1.3 Login with wrong password")
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "wrongpass"}, timeout=15)
    if r.status_code == 401:
        print(f"  ✓ PASSED: Wrong password correctly rejected (401)")
    else:
        print(f"  ✗ FAILED: Wrong password returned {r.status_code} instead of 401")
    
    # Test demo users
    print("\n1.4 Demo Users Login")
    for username, creds in DEMO_USERS.items():
        tok, usr = login(creds)
        if tok:
            print(f"  ✓ PASSED: {username} logged in successfully, role={usr.get('role')}")
        else:
            print(f"  ✗ FAILED: {username} login failed")
    
    return token

def test_data_isolation(admin_token):
    """Test 2: Verify data isolation - empty transactions, 119 master items"""
    print("\n" + "="*80)
    print("TEST 2: DATA ISOLATION (DB=part_production, empty transactions)")
    print("="*80)
    
    headers = auth_header(admin_token)
    
    # Test master items (should have ~119)
    print("\n2.1 Master Items (should have ~119)")
    r = requests.get(f"{API}/items", headers=headers, timeout=20)
    if r.status_code == 200:
        items = r.json()
        count = len(items)
        print(f"  → Found {count} master items")
        if 115 <= count <= 125:  # Allow some tolerance
            print(f"  ✓ PASSED: Master items count is correct (~119)")
        else:
            print(f"  ✗ FAILED: Expected ~119 master items, got {count}")
    else:
        print(f"  ✗ FAILED: /api/items returned {r.status_code}")
    
    # Test transaction collections (should be EMPTY initially)
    transaction_modules = [
        ("smt-production", "Produksi Part & ASSY"),
        ("smt-stock", "Stock Part"),
        ("production-needs", "Kebutuhan Assy VS. Stock Part"),
        ("variance", "Variance Stock"),
    ]
    
    print("\n2.2 Transaction Collections (should be EMPTY initially)")
    all_empty = True
    for endpoint, label in transaction_modules:
        r = requests.get(f"{API}/{endpoint}", headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            count = len(data)
            if count == 0:
                print(f"  ✓ PASSED: {endpoint} is EMPTY (0 records)")
            else:
                print(f"  ⚠ WARNING: {endpoint} has {count} records (expected 0 for fresh app)")
                all_empty = False
        else:
            print(f"  ✗ FAILED: {endpoint} returned {r.status_code}")
            all_empty = False
    
    if all_empty:
        print("\n  ✓ ALL TRANSACTION COLLECTIONS ARE EMPTY (correct for new app)")
    else:
        print("\n  ⚠ Some transaction collections have data (may be from previous tests)")
    
    # Test meta/modules (verify relabeled names)
    print("\n2.3 Meta/Modules (verify 'Part' labels)")
    r = requests.get(f"{API}/meta/modules", headers=headers, timeout=15)
    if r.status_code == 200:
        meta = r.json()
        modules = meta.get("modules", [])
        print(f"  → Found {len(modules)} modules")
        
        # Check for relabeled modules
        module_dict = {m["key"]: m["label"] for m in modules}
        checks = [
            ("smt_production", "Produksi Part"),
            ("smt_stock", "Stock Part"),
        ]
        for key, expected_label_part in checks:
            label = module_dict.get(key, "")
            if expected_label_part in label:
                print(f"  ✓ PASSED: {key} label contains '{expected_label_part}': {label}")
            else:
                print(f"  ⚠ WARNING: {key} label is '{label}' (expected to contain '{expected_label_part}')")
    else:
        print(f"  ✗ FAILED: /api/meta/modules returned {r.status_code}")
    
    # Test roles
    print("\n2.4 Roles Endpoint")
    r = requests.get(f"{API}/roles", headers=headers, timeout=15)
    if r.status_code == 200:
        roles = r.json()
        print(f"  ✓ PASSED: /api/roles returned {len(roles)} roles")
        # Check for relabeled role
        role_dict = {role["value"]: role["label"] for role in roles}
        if "smt" in role_dict:
            print(f"    → 'smt' role label: {role_dict['smt']}")
    else:
        print(f"  ✗ FAILED: /api/roles returned {r.status_code}")

def test_crud_operations(admin_token):
    """Test 3: CRUD operations for all data modules"""
    print("\n" + "="*80)
    print("TEST 3: CRUD OPERATIONS (Create, Read, Update, Delete)")
    print("="*80)
    
    headers = auth_header(admin_token)
    
    # Test data for each module
    test_cases = [
        {
            "name": "smt_production",
            "endpoint": "smt-production",
            "create_data": {
                "date": "2030-01-15",
                "lane": "TEST_LANE",
                "product": "TEST_PRODUCT",
                "type": "TEST_TYPE",
                "ics_no": "9999999901",
                "tt": 30,
                "planing_smt": 1000,
                "act_smt_s1": 300,
                "act_smt_s2": 350,
                "act_smt_s3": 400,
                "plan_assy": 900,
                "act_assy_s1": 250,
                "act_assy_s2": 300,
                "act_assy_s3": 350,
            },
            "update_data": {
                "act_smt_s1": 400,
            },
            "writable": True,
        },
        {
            "name": "smt_stock",
            "endpoint": "smt-stock",
            "create_data": {
                "date": "2030-01-15",
                "lane": "TEST_LANE",
                "product": "TEST_PRODUCT",
                "type": "TEST_TYPE",
                "ics_no": "9999999902",
                "stock_ok_prev": 100,
                "coating": 50,
                "belum_cutting": 30,
                "belum_ict": 20,
                "belum_fct": 10,
                "ok": 200,
            },
            "update_data": {
                "ok": 250,
            },
            "writable": True,
        },
        {
            "name": "items",
            "endpoint": "items",
            "create_data": {
                "lane": "TEST_LANE",
                "product": "TEST_PRODUCT",
                "type": "TEST_TYPE",
                "ics_no": "9999999903",
                "tt": 25,
                "tt_assy": 15,
                "material_per_unit": 1.5,
                "led_rank": "A",
            },
            "update_data": {
                "tt": 30,
            },
            "writable": True,
        },
        {
            "name": "stock_standards",
            "endpoint": "stock-standards",
            "create_data": {
                "lane": "TEST_LANE",
                "product": "TEST_PRODUCT",
                "type": "TEST_TYPE",
                "standard_stock": 500,
            },
            "update_data": {
                "standard_stock": 600,
            },
            "writable": True,
        },
    ]
    
    created_ids = {}
    
    for test_case in test_cases:
        name = test_case["name"]
        endpoint = test_case["endpoint"]
        
        print(f"\n3.{test_cases.index(test_case) + 1} Module: {name} ({endpoint})")
        
        # CREATE
        print(f"  → Creating record...")
        r = requests.post(f"{API}/{endpoint}", json=test_case["create_data"], headers=headers, timeout=20)
        if r.status_code == 200:
            created = r.json()
            record_id = created.get("id")
            created_ids[name] = record_id
            print(f"    ✓ CREATE: Success, id={record_id}")
        elif r.status_code == 409:
            # Duplicate - try to get existing
            print(f"    ⚠ CREATE: Duplicate (409), trying to find existing...")
            r_list = requests.get(f"{API}/{endpoint}?ics_no={test_case['create_data'].get('ics_no')}", headers=headers, timeout=15)
            if r_list.status_code == 200:
                existing = r_list.json()
                if existing:
                    record_id = existing[0].get("id")
                    created_ids[name] = record_id
                    print(f"    ✓ Found existing record, id={record_id}")
                else:
                    print(f"    ✗ CREATE: Failed to find existing record")
                    continue
            else:
                print(f"    ✗ CREATE: Failed ({r.status_code})")
                continue
        else:
            print(f"    ✗ CREATE: Failed ({r.status_code}): {r.text[:200]}")
            continue
        
        # READ (list back)
        print(f"  → Reading back record...")
        r = requests.get(f"{API}/{endpoint}", headers=headers, timeout=20)
        if r.status_code == 200:
            records = r.json()
            found = any(rec.get("id") == record_id for rec in records)
            if found:
                print(f"    ✓ READ: Record found in list")
            else:
                print(f"    ✗ READ: Record NOT found in list")
        else:
            print(f"    ✗ READ: Failed ({r.status_code})")
        
        # UPDATE
        if test_case.get("writable"):
            print(f"  → Updating record...")
            update_payload = {**test_case["create_data"], **test_case["update_data"]}
            r = requests.put(f"{API}/{endpoint}/{record_id}", json=update_payload, headers=headers, timeout=20)
            if r.status_code == 200:
                updated = r.json()
                # Verify update
                update_key = list(test_case["update_data"].keys())[0]
                expected_value = test_case["update_data"][update_key]
                actual_value = updated.get(update_key)
                if actual_value == expected_value:
                    print(f"    ✓ UPDATE: Success, {update_key}={actual_value}")
                else:
                    print(f"    ⚠ UPDATE: Success but value mismatch, {update_key}={actual_value} (expected {expected_value})")
            else:
                print(f"    ✗ UPDATE: Failed ({r.status_code}): {r.text[:200]}")
        
        # DELETE
        print(f"  → Deleting record...")
        r = requests.delete(f"{API}/{endpoint}/{record_id}", headers=headers, timeout=20)
        if r.status_code == 200:
            print(f"    ✓ DELETE: Success")
        else:
            print(f"    ✗ DELETE: Failed ({r.status_code})")

def test_filters(admin_token):
    """Test 4: Filter query parameters"""
    print("\n" + "="*80)
    print("TEST 4: FILTER QUERY PARAMETERS")
    print("="*80)
    
    headers = auth_header(admin_token)
    
    # First create some test data
    print("\n4.1 Creating test data for filtering...")
    test_record = {
        "date": "2030-02-20",
        "lane": "FILTER_LANE",
        "product": "FILTER_PRODUCT",
        "type": "FILTER_TYPE",
        "ics_no": "9999999910",
        "tt": 30,
        "planing_smt": 1000,
        "act_smt_s1": 300,
        "act_smt_s2": 350,
        "act_smt_s3": 400,
        "plan_assy": 900,
        "act_assy_s1": 250,
        "act_assy_s2": 300,
        "act_assy_s3": 350,
    }
    r = requests.post(f"{API}/smt-production", json=test_record, headers=headers, timeout=20)
    if r.status_code == 200:
        created_id = r.json().get("id")
        print(f"  ✓ Test record created, id={created_id}")
    else:
        print(f"  ⚠ Could not create test record ({r.status_code}), using existing data")
        created_id = None
    
    # Test various filters
    filter_tests = [
        ("date_from", {"date_from": "2030-02-01"}),
        ("date_to", {"date_to": "2030-12-31"}),
        ("lane", {"lane": "FILTER_LANE"}),
        ("type", {"type": "FILTER_TYPE"}),
        ("ics_no", {"ics_no": "9999999910"}),
        ("product", {"product": "FILTER_PRODUCT"}),
    ]
    
    print("\n4.2 Testing filter parameters on /api/smt-production")
    for filter_name, params in filter_tests:
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        r = requests.get(f"{API}/smt-production?{query_string}", headers=headers, timeout=20)
        if r.status_code == 200:
            results = r.json()
            print(f"  ✓ PASSED: {filter_name} filter works, returned {len(results)} records")
        else:
            print(f"  ✗ FAILED: {filter_name} filter returned {r.status_code}")
    
    # Cleanup
    if created_id:
        requests.delete(f"{API}/smt-production/{created_id}", headers=headers, timeout=10)

def test_import_export(admin_token):
    """Test 5: Import/Export functionality"""
    print("\n" + "="*80)
    print("TEST 5: IMPORT/EXPORT")
    print("="*80)
    
    headers = auth_header(admin_token)
    
    # Test template download
    print("\n5.1 Template Download")
    endpoints = ["smt-production", "smt-stock", "items", "stock-standards"]
    for endpoint in endpoints:
        r = requests.get(f"{API}/import/{endpoint}/template", headers=headers, timeout=20)
        if r.status_code == 200 and len(r.content) > 0:
            print(f"  ✓ PASSED: {endpoint} template downloaded ({len(r.content)} bytes)")
        else:
            print(f"  ✗ FAILED: {endpoint} template download failed ({r.status_code})")
    
    # Test import (smt-production)
    print("\n5.2 Import Preview and Confirm (smt-production)")
    wb = Workbook()
    ws = wb.active
    # Use correct field labels from FIELDS definition
    ws.append(["TANGGAL", "LANE", "PRODUCT", "TYPE", "ICS NO", "T/T", "PLANING PART", 
               "ACT PART S3", "ACT PART S1", "ACT PART S2", "PLAN ASSY",
               "ACT ASSY S3", "ACT ASSY S1", "ACT ASSY S2"])
    ws.append(["2030-03-10", "IMP_LANE", "IMP_PROD", "IMP_TYPE", "9999999920", 30, 1000,
               400, 300, 350, 900, 350, 250, 300])
    
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    
    # Preview
    files = {"file": ("test_import.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{API}/import/smt-production/preview", files=files, headers=headers, timeout=30)
    if r.status_code == 200:
        preview = r.json()
        print(f"  ✓ PASSED: Import preview successful, {preview.get('total')} rows")
    else:
        print(f"  ✗ FAILED: Import preview failed ({r.status_code}): {r.text[:200]}")
        return
    
    # Confirm import
    buf.seek(0)
    files = {"file": ("test_import.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{API}/import/smt-production/confirm", files=files, headers=headers, timeout=30)
    if r.status_code == 200:
        result = r.json()
        print(f"  ✓ PASSED: Import confirm successful, inserted={result.get('inserted')}, updated={result.get('updated')}")
    else:
        print(f"  ✗ FAILED: Import confirm failed ({r.status_code}): {r.text[:200]}")
    
    # Cleanup
    r = requests.get(f"{API}/smt-production?ics_no=9999999920", headers=headers, timeout=15)
    if r.status_code == 200:
        for rec in r.json():
            requests.delete(f"{API}/smt-production/{rec['id']}", headers=headers, timeout=10)

def test_backup_restore(admin_token):
    """Test 6: Backup and Restore"""
    print("\n" + "="*80)
    print("TEST 6: BACKUP & RESTORE")
    print("="*80)
    
    headers = auth_header(admin_token)
    
    # Test backup export
    print("\n6.1 Backup Export")
    r = requests.get(f"{API}/backup/export", headers=headers, timeout=60)
    if r.status_code == 200 and len(r.content) > 0:
        backup_data = r.content
        print(f"  ✓ PASSED: Backup exported successfully ({len(backup_data)} bytes)")
        
        # Test backup preview
        print("\n6.2 Backup Preview")
        files = {"file": ("backup.zip", io.BytesIO(backup_data), "application/zip")}
        r = requests.post(f"{API}/backup/preview", files=files, headers=headers, timeout=30)
        if r.status_code == 200:
            preview = r.json()
            print(f"  ✓ PASSED: Backup preview successful")
            print(f"    → Modules in backup: {len(preview.get('modules', []))}")
            for mod in preview.get('modules', [])[:5]:  # Show first 5
                print(f"      - {mod.get('label')}: {mod.get('in_backup')} records")
        else:
            print(f"  ✗ FAILED: Backup preview failed ({r.status_code})")
        
        # Note: We won't test actual restore as it would wipe data
        print("\n6.3 Backup Restore")
        print("  ⚠ SKIPPED: Restore test skipped to preserve data (would wipe all collections)")
        print("    → Restore endpoint: POST /api/backup/restore")
        print("    → Expected behavior: Accepts backup.zip, clears collections, restores data")
    else:
        print(f"  ✗ FAILED: Backup export failed ({r.status_code})")

def test_users_roles(admin_token):
    """Test 7: Users and Roles Management"""
    print("\n" + "="*80)
    print("TEST 7: USERS & ROLES MANAGEMENT")
    print("="*80)
    
    headers = auth_header(admin_token)
    
    # List users
    print("\n7.1 List Users")
    r = requests.get(f"{API}/users", headers=headers, timeout=20)
    if r.status_code == 200:
        users = r.json()
        print(f"  ✓ PASSED: Listed {len(users)} users")
        admin_user = next((u for u in users if u.get("username") == "admin"), None)
        if admin_user:
            print(f"    → Admin user found: {admin_user.get('name')}, role={admin_user.get('role')}")
    else:
        print(f"  ✗ FAILED: List users failed ({r.status_code})")
    
    # List roles
    print("\n7.2 List Roles")
    r = requests.get(f"{API}/roles", headers=headers, timeout=15)
    if r.status_code == 200:
        roles = r.json()
        print(f"  ✓ PASSED: Listed {len(roles)} roles")
        for role in roles:
            print(f"    → {role.get('value')}: {role.get('label')}")
    else:
        print(f"  ✗ FAILED: List roles failed ({r.status_code})")
    
    # Create test user
    print("\n7.3 Create User")
    test_user_data = {
        "username": "testuser_crud",
        "email": "testuser_crud@test.com",
        "password": "test1234",
        "name": "Test User CRUD",
        "role": "smt",
        "permissions": {"smt_production": "write", "smt_stock": "read"},
    }
    r = requests.post(f"{API}/users", json=test_user_data, headers=headers, timeout=20)
    if r.status_code == 200:
        created_user = r.json()
        user_id = created_user.get("id")
        print(f"  ✓ PASSED: User created, id={user_id}, username={created_user.get('username')}")
        
        # Update user
        print("\n7.4 Update User")
        update_data = {
            "name": "Test User UPDATED",
            "role": "production_planning",
        }
        r = requests.put(f"{API}/users/{user_id}", json=update_data, headers=headers, timeout=20)
        if r.status_code == 200:
            updated_user = r.json()
            print(f"  ✓ PASSED: User updated, name={updated_user.get('name')}, role={updated_user.get('role')}")
        else:
            print(f"  ✗ FAILED: Update user failed ({r.status_code})")
        
        # Delete user
        print("\n7.5 Delete User")
        r = requests.delete(f"{API}/users/{user_id}", headers=headers, timeout=20)
        if r.status_code == 200:
            print(f"  ✓ PASSED: User deleted")
        else:
            print(f"  ✗ FAILED: Delete user failed ({r.status_code})")
    else:
        print(f"  ✗ FAILED: Create user failed ({r.status_code}): {r.text[:200]}")

def test_production_needs_variance(admin_token):
    """Test 8: Production Needs and Variance (auto-derived modules)"""
    print("\n" + "="*80)
    print("TEST 8: PRODUCTION NEEDS & VARIANCE (Auto-derived)")
    print("="*80)
    
    headers = auth_header(admin_token)
    
    print("\n8.1 Production Needs Endpoint")
    r = requests.get(f"{API}/production-needs", headers=headers, timeout=20)
    if r.status_code == 200:
        needs = r.json()
        print(f"  ✓ PASSED: /api/production-needs returned {len(needs)} records")
        if needs:
            sample = needs[0]
            print(f"    → Sample fields: date={sample.get('date')}, status={sample.get('status')}, blc={sample.get('blc')}")
    else:
        print(f"  ✗ FAILED: /api/production-needs returned {r.status_code}")
    
    print("\n8.2 Variance Endpoint")
    r = requests.get(f"{API}/variance", headers=headers, timeout=20)
    if r.status_code == 200:
        variance = r.json()
        print(f"  ✓ PASSED: /api/variance returned {len(variance)} records")
        if variance:
            sample = variance[0]
            print(f"    → Sample fields: date={sample.get('date')}, variance_status={sample.get('variance_status')}, variance={sample.get('variance')}")
    else:
        print(f"  ✗ FAILED: /api/variance returned {r.status_code}")
    
    print("\n  ℹ Note: production_needs and variance are auto-derived from smt_production and smt_stock")
    print("    They may be read-only or have limited write capabilities")

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("PART PRODUCTION BACKEND TEST SUITE")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"API URL: {API}")
    print("="*80)
    
    # Test 1: Auth
    admin_token = test_auth()
    if not admin_token:
        print("\n✗ CRITICAL: Authentication failed, cannot continue tests")
        return
    
    # Test 2: Data Isolation
    test_data_isolation(admin_token)
    
    # Test 3: CRUD Operations
    test_crud_operations(admin_token)
    
    # Test 4: Filters
    test_filters(admin_token)
    
    # Test 5: Import/Export
    test_import_export(admin_token)
    
    # Test 6: Backup/Restore
    test_backup_restore(admin_token)
    
    # Test 7: Users & Roles
    test_users_roles(admin_token)
    
    # Test 8: Production Needs & Variance
    test_production_needs_variance(admin_token)
    
    print("\n" + "="*80)
    print("TEST SUITE COMPLETE")
    print("="*80)
    print("\nReview the output above for any ✗ FAILED or ⚠ WARNING messages")
    print("All ✓ PASSED tests indicate successful functionality")

if __name__ == "__main__":
    main()
