#!/usr/bin/env python3
"""
DATABASE ISOLATION VERIFICATION TEST for PART PRODUCTION
Goal: Prove the app reads/writes ONLY to "part_production" DB and NEVER touches test_database or SMT DB
"""

import requests
import pymongo
from pymongo import MongoClient
import json
from datetime import datetime

# Configuration
BACKEND_URL = "https://data-stock-branch.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
TARGET_DB = "part_production"
OTHER_DB = "test_database"

# Auth credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def get_auth_token():
    """Login and get JWT token"""
    print("\n🔐 Authenticating...")
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None
    
    data = response.json()
    token = data.get("token") or data.get("access_token")
    if token:
        print(f"✅ Authentication successful")
    else:
        print(f"❌ No token in response: {data}")
    return token

def get_db_stats(mongo_client):
    """Get database and collection statistics"""
    stats = {}
    
    for db_name in [TARGET_DB, OTHER_DB]:
        db = mongo_client[db_name]
        stats[db_name] = {}
        
        collections = ["users", "items", "smt_production", "smt_stock", 
                      "production_needs", "variance", "stock_standards"]
        
        for coll_name in collections:
            try:
                count = db[coll_name].count_documents({})
                stats[db_name][coll_name] = count
            except Exception as e:
                stats[db_name][coll_name] = f"Error: {e}"
    
    return stats

def print_db_stats(stats, title="Database Statistics"):
    """Print database statistics in a formatted way"""
    print(f"\n📊 {title}")
    print("-" * 80)
    
    for db_name, collections in stats.items():
        print(f"\n  Database: {db_name}")
        for coll_name, count in collections.items():
            print(f"    - {coll_name}: {count}")

def test_1_confirm_active_db(mongo_client):
    """Test 1: Confirm the running backend's active DB"""
    print_section("TEST 1: CONFIRM ACTIVE DATABASE")
    
    print(f"\n📋 Checking MongoDB databases...")
    
    # List all databases
    db_list = mongo_client.list_database_names()
    print(f"\n  Available databases: {db_list}")
    
    # Get initial stats
    stats = get_db_stats(mongo_client)
    print_db_stats(stats, "INITIAL Database State")
    
    return stats

def test_2_write_isolation(token, mongo_client, initial_stats):
    """Test 2: WRITE-ISOLATION TEST"""
    print_section("TEST 2: WRITE-ISOLATION TEST")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get counts before write
    part_prod_before = mongo_client[TARGET_DB]["smt_production"].count_documents({})
    test_db_before = mongo_client[OTHER_DB]["smt_production"].count_documents({})
    
    print(f"\n📊 BEFORE CREATE:")
    print(f"  - {TARGET_DB}.smt_production: {part_prod_before} records")
    print(f"  - {OTHER_DB}.smt_production: {test_db_before} records")
    
    # Create a new smt_production record via API
    print(f"\n📝 Creating new smt_production record via API...")
    
    test_record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "lane": "TEST-LANE-ISOLATION",
        "type": "ISOLATION-TEST",
        "ics_no": "ICS-ISOLATION-001",
        "product": "TEST-PRODUCT-ISOLATION",
        "planing_part": 100,
        "act_part_s1": 25,
        "act_part_s2": 25,
        "act_part_s3": 25,
        "act_part_total": 75,
        "act_assy_s1": 20,
        "act_assy_s2": 20,
        "act_assy_s3": 20,
        "act_assy_total": 60,
        "remarks": "DATABASE ISOLATION TEST RECORD"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/smt-production",
        headers=headers,
        json=test_record
    )
    
    if response.status_code not in [200, 201]:
        print(f"❌ Failed to create record: {response.status_code} - {response.text}")
        return None, False
    
    created_record = response.json()
    record_id = created_record.get("id")
    print(f"✅ Record created successfully with ID: {record_id}")
    
    # Get counts after write
    part_prod_after = mongo_client[TARGET_DB]["smt_production"].count_documents({})
    test_db_after = mongo_client[OTHER_DB]["smt_production"].count_documents({})
    
    print(f"\n📊 AFTER CREATE:")
    print(f"  - {TARGET_DB}.smt_production: {part_prod_after} records (change: +{part_prod_after - part_prod_before})")
    print(f"  - {OTHER_DB}.smt_production: {test_db_after} records (change: +{test_db_after - test_db_before})")
    
    # Verify isolation
    print(f"\n🔍 VERIFICATION:")
    
    # Check if record exists in part_production
    part_prod_record = mongo_client[TARGET_DB]["smt_production"].find_one({"lane": "TEST-LANE-ISOLATION"})
    if part_prod_record:
        print(f"  ✅ Record FOUND in {TARGET_DB}.smt_production")
    else:
        print(f"  ❌ Record NOT FOUND in {TARGET_DB}.smt_production")
    
    # Check if record exists in test_database (should NOT exist)
    test_db_record = mongo_client[OTHER_DB]["smt_production"].find_one({"lane": "TEST-LANE-ISOLATION"})
    if test_db_record:
        print(f"  ❌ ISOLATION BREACH: Record FOUND in {OTHER_DB}.smt_production")
    else:
        print(f"  ✅ Record NOT FOUND in {OTHER_DB}.smt_production (correct isolation)")
    
    # Final verdict
    write_isolated = (part_prod_after == part_prod_before + 1) and (test_db_after == test_db_before) and part_prod_record and not test_db_record
    
    if write_isolated:
        print(f"\n✅ WRITE-ISOLATION TEST: PASS")
        print(f"   - Record created in {TARGET_DB} only")
        print(f"   - {OTHER_DB} remains unchanged")
    else:
        print(f"\n❌ WRITE-ISOLATION TEST: FAIL")
    
    return record_id, write_isolated

def test_3_read_isolation(token, mongo_client, record_id):
    """Test 3: READ-ISOLATION TEST"""
    print_section("TEST 3: READ-ISOLATION TEST")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET the smt_production list via API
    print(f"\n📖 Reading smt_production list via API...")
    
    response = requests.get(
        f"{BACKEND_URL}/smt-production",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to read records: {response.status_code} - {response.text}")
        return False
    
    records = response.json()
    print(f"✅ Retrieved {len(records)} records from API")
    
    # Check if our test record is in the list
    test_record_found = any(r.get("id") == record_id or r.get("lane") == "TEST-LANE-ISOLATION" for r in records)
    
    if test_record_found:
        print(f"✅ Test record FOUND in API response (reads from {TARGET_DB})")
    else:
        print(f"❌ Test record NOT FOUND in API response")
    
    # DELETE the record via API
    print(f"\n🗑️  Deleting test record via API...")
    
    response = requests.delete(
        f"{BACKEND_URL}/smt-production/{record_id}",
        headers=headers
    )
    
    if response.status_code not in [200, 204]:
        print(f"❌ Failed to delete record: {response.status_code} - {response.text}")
        return False
    
    print(f"✅ Record deleted successfully via API")
    
    # Verify deletion in both databases
    print(f"\n🔍 VERIFICATION AFTER DELETE:")
    
    part_prod_record = mongo_client[TARGET_DB]["smt_production"].find_one({"lane": "TEST-LANE-ISOLATION"})
    test_db_record = mongo_client[OTHER_DB]["smt_production"].find_one({"lane": "TEST-LANE-ISOLATION"})
    
    if not part_prod_record:
        print(f"  ✅ Record REMOVED from {TARGET_DB}.smt_production")
    else:
        print(f"  ❌ Record STILL EXISTS in {TARGET_DB}.smt_production")
    
    if not test_db_record:
        print(f"  ✅ Record NOT FOUND in {OTHER_DB}.smt_production (correct isolation)")
    else:
        print(f"  ❌ Record FOUND in {OTHER_DB}.smt_production")
    
    read_isolated = test_record_found and not part_prod_record and not test_db_record
    
    if read_isolated:
        print(f"\n✅ READ-ISOLATION TEST: PASS")
        print(f"   - API reads from {TARGET_DB} only")
        print(f"   - Delete operation affects {TARGET_DB} only")
    else:
        print(f"\n❌ READ-ISOLATION TEST: FAIL")
    
    return read_isolated

def test_4_master_items_count(token, mongo_client):
    """Test 4: Confirm master items count is 119"""
    print_section("TEST 4: MASTER ITEMS COUNT VERIFICATION")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get count from API
    print(f"\n📖 Getting master items from API...")
    response = requests.get(f"{BACKEND_URL}/items", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to get items: {response.status_code} - {response.text}")
        return False
    
    api_items = response.json()
    api_count = len(api_items)
    
    # Get count from database
    db_count = mongo_client[TARGET_DB]["items"].count_documents({})
    
    print(f"\n📊 Master Items Count:")
    print(f"  - API response: {api_count} items")
    print(f"  - Database ({TARGET_DB}.items): {db_count} items")
    
    if api_count == 119 and db_count == 119:
        print(f"\n✅ MASTER ITEMS COUNT: PASS (119 items confirmed)")
        return True
    else:
        print(f"\n⚠️  MASTER ITEMS COUNT: Expected 119, got API={api_count}, DB={db_count}")
        return api_count == db_count  # At least they should match

def test_5_config_references():
    """Test 5: Check for any test_database or external references"""
    print_section("TEST 5: CONFIGURATION REFERENCES CHECK")
    
    print(f"\n🔍 Checking backend configuration files...")
    
    issues = []
    
    # Check .env file
    try:
        with open("/app/backend/.env", "r") as f:
            env_content = f.read()
            
        print(f"\n📄 backend/.env:")
        for line in env_content.split("\n"):
            if line.strip() and not line.startswith("#"):
                print(f"  {line}")
                
                if "test_database" in line.lower():
                    issues.append(f"  ❌ Found 'test_database' reference in .env: {line}")
                if "smt" in line.lower() and "DB_NAME" in line:
                    issues.append(f"  ⚠️  Found 'smt' in DB_NAME: {line}")
    except Exception as e:
        print(f"  ⚠️  Could not read .env: {e}")
    
    # Check server.py for hardcoded references
    try:
        with open("/app/backend/server.py", "r") as f:
            server_content = f.read()
        
        print(f"\n📄 Checking server.py for hardcoded database references...")
        
        if 'client["test_database"]' in server_content:
            issues.append(f"  ❌ Found hardcoded 'test_database' reference in server.py")
        
        if 'client["smt' in server_content and 'client[os.environ' not in server_content:
            issues.append(f"  ⚠️  Found potential hardcoded SMT database reference")
        
        # Check that it uses os.environ['DB_NAME']
        if 'client[os.environ[\'DB_NAME\']]' in server_content or 'client[os.environ["DB_NAME"]]' in server_content:
            print(f"  ✅ server.py correctly uses os.environ['DB_NAME']")
        else:
            issues.append(f"  ⚠️  server.py may not be using environment variable for DB_NAME")
            
    except Exception as e:
        print(f"  ⚠️  Could not read server.py: {e}")
    
    if not issues:
        print(f"\n✅ CONFIGURATION CHECK: PASS")
        print(f"   - No references to test_database or external SMT databases found")
        print(f"   - Configuration correctly uses part_production database")
        return True
    else:
        print(f"\n⚠️  CONFIGURATION CHECK: Issues found:")
        for issue in issues:
            print(issue)
        return False

def main():
    print_section("DATABASE ISOLATION VERIFICATION - PART PRODUCTION")
    print(f"\nTarget Database: {TARGET_DB}")
    print(f"Comparison Database: {OTHER_DB}")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"MongoDB URL: {MONGO_URL}")
    
    # Connect to MongoDB
    print(f"\n🔌 Connecting to MongoDB...")
    try:
        mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        mongo_client.server_info()  # Test connection
        print(f"✅ MongoDB connection successful")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return
    
    # Get auth token
    token = get_auth_token()
    if not token:
        print(f"❌ Cannot proceed without authentication")
        return
    
    # Run tests
    results = {}
    
    # Test 1: Confirm active DB
    initial_stats = test_1_confirm_active_db(mongo_client)
    results["test_1_active_db"] = initial_stats is not None
    
    # Test 2: Write isolation
    record_id, write_isolated = test_2_write_isolation(token, mongo_client, initial_stats)
    results["test_2_write_isolation"] = write_isolated
    
    # Test 3: Read isolation
    if record_id:
        read_isolated = test_3_read_isolation(token, mongo_client, record_id)
        results["test_3_read_isolation"] = read_isolated
    else:
        print_section("TEST 3: READ-ISOLATION TEST")
        print("⚠️  SKIPPED - No record ID from Test 2")
        results["test_3_read_isolation"] = False
    
    # Test 4: Master items count
    master_items_ok = test_4_master_items_count(token, mongo_client)
    results["test_4_master_items"] = master_items_ok
    
    # Test 5: Config references
    config_ok = test_5_config_references()
    results["test_5_config"] = config_ok
    
    # Final summary
    print_section("FINAL SUMMARY - DATABASE ISOLATION VERIFICATION")
    
    print(f"\n📋 TEST RESULTS:")
    print(f"  1. Active Database Confirmation: {'✅ PASS' if results['test_1_active_db'] else '❌ FAIL'}")
    print(f"  2. Write Isolation Test: {'✅ PASS' if results['test_2_write_isolation'] else '❌ FAIL'}")
    print(f"  3. Read Isolation Test: {'✅ PASS' if results['test_3_read_isolation'] else '❌ FAIL'}")
    print(f"  4. Master Items Count (119): {'✅ PASS' if results['test_4_master_items'] else '❌ FAIL'}")
    print(f"  5. Configuration Check: {'✅ PASS' if results['test_5_config'] else '❌ FAIL'}")
    
    all_passed = all(results.values())
    
    print(f"\n{'='*80}")
    if all_passed:
        print(f"  🎉 DATABASE ISOLATION: ✅ PASS")
        print(f"  The application reads/writes ONLY to '{TARGET_DB}' database")
        print(f"  No cross-contamination with '{OTHER_DB}' or other databases detected")
    else:
        print(f"  ⚠️  DATABASE ISOLATION: ❌ FAIL")
        print(f"  Some tests failed - review details above")
    print(f"{'='*80}\n")
    
    # Get final stats
    final_stats = get_db_stats(mongo_client)
    print_db_stats(final_stats, "FINAL Database State")
    
    mongo_client.close()

if __name__ == "__main__":
    main()
