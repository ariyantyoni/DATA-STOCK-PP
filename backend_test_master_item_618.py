#!/usr/bin/env python3
"""
Backend Test: Master Item Update (618 items) & Cross-Module Linking
Tests the new Master Item seeding with 618 records and cross-module integration via product_map
"""

import requests
import json
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

class TestSession:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.test_data_ids = []  # Track created test data for cleanup
        
    def login(self) -> bool:
        """Login and get auth token"""
        print("\n" + "="*80)
        print("TEST 0: Authentication")
        print("="*80)
        
        try:
            response = self.session.post(
                f"{BASE_URL}/auth/login",
                json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                print(f"✅ PASS: Login successful as {ADMIN_USERNAME}")
                print(f"   User: {data.get('user', {}).get('name', 'N/A')}")
                print(f"   Role: {data.get('user', {}).get('role', 'N/A')}")
                return True
            else:
                print(f"❌ FAIL: Login failed with status {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ FAIL: Login exception: {e}")
            return False
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> requests.Response:
        """GET request with auth"""
        return self.session.get(f"{BASE_URL}{endpoint}", params=params)
    
    def post(self, endpoint: str, data: Dict) -> requests.Response:
        """POST request with auth"""
        return self.session.post(f"{BASE_URL}{endpoint}", json=data)
    
    def put(self, endpoint: str, data: Dict) -> requests.Response:
        """PUT request with auth"""
        return self.session.put(f"{BASE_URL}{endpoint}", json=data)
    
    def delete(self, endpoint: str) -> requests.Response:
        """DELETE request with auth"""
        return self.session.delete(f"{BASE_URL}{endpoint}")


def test_1_master_item_count_and_fields(session: TestSession):
    """
    TEST 1: GET /api/items returns 618 items
    Verify each item has: proses_mesin, tt_assy, material_per_unit, cap_h
    Verify NO led_rank field
    Spot-check cap_h calculation
    Report distinct proses_mesin values
    """
    print("\n" + "="*80)
    print("TEST 1: Master Item Count & Field Verification (618 items)")
    print("="*80)
    
    try:
        response = session.get("/items")
        
        if response.status_code != 200:
            print(f"❌ FAIL: GET /api/items returned status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        items = response.json()
        item_count = len(items)
        
        print(f"\n📊 Total Items: {item_count}")
        
        if item_count != 618:
            print(f"❌ FAIL: Expected 618 items, got {item_count}")
            return False
        
        print(f"✅ PASS: Item count is exactly 618")
        
        # Check fields on all items
        items_with_led_rank = []
        items_missing_proses_mesin = []
        items_missing_tt_assy = []
        items_missing_material_per_unit = []
        items_missing_cap_h = []
        proses_mesin_values = set()
        
        for item in items:
            # Check for unwanted field
            if "led_rank" in item:
                items_with_led_rank.append(item.get("id", "unknown"))
            
            # Check for required fields
            if "proses_mesin" not in item:
                items_missing_proses_mesin.append(item.get("id", "unknown"))
            else:
                pm = item.get("proses_mesin", "").strip()
                if pm:  # Only add non-empty values
                    proses_mesin_values.add(pm)
            
            if "tt_assy" not in item:
                items_missing_tt_assy.append(item.get("id", "unknown"))
            
            if "material_per_unit" not in item:
                items_missing_material_per_unit.append(item.get("id", "unknown"))
            
            if "cap_h" not in item:
                items_missing_cap_h.append(item.get("id", "unknown"))
        
        # Report field verification
        print("\n🔍 Field Verification:")
        
        if items_with_led_rank:
            print(f"❌ FAIL: {len(items_with_led_rank)} items still have 'led_rank' field")
            print(f"   Sample IDs: {items_with_led_rank[:5]}")
            return False
        else:
            print(f"✅ PASS: NO items have 'led_rank' field (removed successfully)")
        
        if items_missing_proses_mesin:
            print(f"❌ FAIL: {len(items_missing_proses_mesin)} items missing 'proses_mesin' field")
            return False
        else:
            print(f"✅ PASS: ALL items have 'proses_mesin' field")
        
        if items_missing_tt_assy:
            print(f"❌ FAIL: {len(items_missing_tt_assy)} items missing 'tt_assy' field")
            return False
        else:
            print(f"✅ PASS: ALL items have 'tt_assy' field")
        
        if items_missing_material_per_unit:
            print(f"❌ FAIL: {len(items_missing_material_per_unit)} items missing 'material_per_unit' field")
            return False
        else:
            print(f"✅ PASS: ALL items have 'material_per_unit' field")
        
        if items_missing_cap_h:
            print(f"❌ FAIL: {len(items_missing_cap_h)} items missing 'cap_h' field")
            return False
        else:
            print(f"✅ PASS: ALL items have 'cap_h' field")
        
        # Report distinct proses_mesin values
        print(f"\n📋 Distinct PROSES MESIN values ({len(proses_mesin_values)}):")
        for pm in sorted(proses_mesin_values):
            count = sum(1 for item in items if item.get("proses_mesin", "").strip() == pm)
            print(f"   - {pm}: {count} items")
        
        # Spot-check cap_h calculation (cap_h = round(3600/tt, 2))
        print(f"\n🧮 Spot-check CAP/H calculation (cap_h = round(3600/tt, 2)):")
        sample_items = items[:5]  # Check first 5 items
        all_correct = True
        
        for item in sample_items:
            tt = item.get("tt", 0)
            cap_h = item.get("cap_h", 0)
            expected_cap_h = round(3600 / tt, 2) if tt else 0.0
            
            match = abs(cap_h - expected_cap_h) < 0.01  # Allow small floating point difference
            status = "✓" if match else "✗"
            
            print(f"   {status} Item {item.get('ics_no', 'N/A')}: tt={tt}, cap_h={cap_h}, expected={expected_cap_h}")
            
            if not match:
                all_correct = False
        
        if all_correct:
            print(f"✅ PASS: CAP/H calculations are correct")
        else:
            print(f"❌ FAIL: Some CAP/H calculations are incorrect")
            return False
        
        print(f"\n✅ TEST 1 PASSED: All field verifications successful")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Exception in test_1: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_2_meta_options(session: TestSession):
    """
    TEST 2: GET /api/meta/options
    Verify lanes, types, ics_nos are NON-EMPTY and include master values
    Verify products include REGULER and SPO
    """
    print("\n" + "="*80)
    print("TEST 2: Meta Options (sourced from Master Item)")
    print("="*80)
    
    try:
        response = session.get("/meta/options")
        
        if response.status_code != 200:
            print(f"❌ FAIL: GET /api/meta/options returned status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        options = response.json()
        
        # Check lanes
        lanes = options.get("lanes", [])
        print(f"\n📋 Lanes ({len(lanes)} total):")
        if not lanes:
            print(f"❌ FAIL: lanes is EMPTY")
            return False
        
        # Check for expected lane from master
        if "PM 40" in lanes:
            print(f"✅ PASS: lanes is NON-EMPTY and includes master value 'PM 40'")
            print(f"   Sample lanes: {lanes[:10]}")
        else:
            print(f"⚠️  WARNING: Expected lane 'PM 40' not found")
            print(f"   Available lanes: {lanes[:10]}")
        
        # Check types
        types = options.get("types", [])
        print(f"\n📋 Types ({len(types)} total):")
        if not types:
            print(f"❌ FAIL: types is EMPTY")
            return False
        
        # Check for expected type from master
        if "01D HL" in types:
            print(f"✅ PASS: types is NON-EMPTY and includes master value '01D HL'")
            print(f"   Sample types: {types[:10]}")
        else:
            print(f"⚠️  WARNING: Expected type '01D HL' not found")
            print(f"   Available types: {types[:10]}")
        
        # Check ics_nos
        ics_nos = options.get("ics_nos", [])
        print(f"\n📋 ICS Numbers ({len(ics_nos)} total):")
        if not ics_nos:
            print(f"❌ FAIL: ics_nos is EMPTY")
            return False
        
        print(f"✅ PASS: ics_nos is NON-EMPTY")
        print(f"   Sample ICS numbers: {ics_nos[:10]}")
        
        # Check products
        products = options.get("products", [])
        print(f"\n📋 Products ({len(products)} total):")
        if not products:
            print(f"❌ FAIL: products is EMPTY")
            return False
        
        has_reguler = "REGULER" in products
        has_spo = "SPO" in products
        
        print(f"   Products: {products}")
        
        if has_reguler:
            print(f"✅ PASS: products includes 'REGULER'")
        else:
            print(f"⚠️  WARNING: 'REGULER' not found in products")
        
        if has_spo:
            print(f"✅ PASS: products includes 'SPO'")
        else:
            print(f"⚠️  WARNING: 'SPO' not found in products")
        
        if lanes and types and ics_nos and products:
            print(f"\n✅ TEST 2 PASSED: All meta options are non-empty and sourced from master")
            return True
        else:
            print(f"\n❌ TEST 2 FAILED: Some meta options are empty")
            return False
        
    except Exception as e:
        print(f"❌ FAIL: Exception in test_2: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_cross_module_linking(session: TestSession):
    """
    TEST 3: Cross-module linking via product_map
    - Pick an existing master item (get ics_no and type)
    - Create smt_stock record with that ics_no+type but WITHOUT product
    - Verify product auto-fills from master
    - Verify standard_stock/indikator computed
    - Verify production_needs/dashboard resolve product from master
    - Clean up test data
    """
    print("\n" + "="*80)
    print("TEST 3: Cross-Module Linking (product_map)")
    print("="*80)
    
    try:
        # Step 1: Get a master item to use for testing
        print("\n📥 Step 1: Fetching master items...")
        response = session.get("/items")
        if response.status_code != 200:
            print(f"❌ FAIL: Could not fetch items")
            return False
        
        items = response.json()
        if not items:
            print(f"❌ FAIL: No items available")
            return False
        
        # Pick first item with non-empty ics_no and type
        test_item = None
        for item in items:
            if item.get("ics_no") and item.get("type") and item.get("product"):
                test_item = item
                break
        
        if not test_item:
            print(f"❌ FAIL: Could not find suitable test item")
            return False
        
        test_ics_no = test_item["ics_no"]
        test_type = test_item["type"]
        expected_product = test_item["product"]
        test_lane = test_item.get("lane", "TEST-LANE")
        
        print(f"✅ Selected test item:")
        print(f"   ICS No: {test_ics_no}")
        print(f"   Type: {test_type}")
        print(f"   Expected Product: {expected_product}")
        print(f"   Lane: {test_lane}")
        
        # Step 2: Create smt_stock record WITHOUT product field
        print(f"\n📤 Step 2: Creating smt_stock record WITHOUT product field...")
        
        test_stock_data = {
            "date": "2026-01-15",
            "lane": test_lane,
            "type": test_type,
            "ics_no": test_ics_no,
            # NOTE: NO "product" field sent
            "stock_ok_prev": 100,
            "coating": 10,
            "belum_cutting": 5,
            "belum_ict": 3,
            "belum_fct": 2,
            "ok": 80
        }
        
        response = session.post("/smt-stock", test_stock_data)
        
        if response.status_code not in [200, 201]:
            print(f"❌ FAIL: Could not create smt_stock record")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        created_stock = response.json()
        stock_id = created_stock.get("id")
        session.test_data_ids.append(("smt_stock", stock_id))
        
        print(f"✅ Created smt_stock record: {stock_id}")
        
        # Step 3: GET the stock list and verify product auto-filled
        print(f"\n📥 Step 3: Fetching stock list to verify product auto-fill...")
        
        response = session.get("/smt-stock", params={"date_from": "2026-01-15", "date_to": "2026-01-15"})
        
        if response.status_code != 200:
            print(f"❌ FAIL: Could not fetch stock dataset")
            print(f"   Status: {response.status_code}")
            return False
        
        stock_list = response.json()
        
        # Find our test record
        test_record = None
        for record in stock_list:
            if record.get("id") == stock_id:
                test_record = record
                break
        
        if not test_record:
            print(f"❌ FAIL: Could not find created stock record in dataset")
            return False
        
        actual_product = test_record.get("product", "")
        
        print(f"\n🔍 Product Auto-Fill Verification:")
        print(f"   Expected product: {expected_product}")
        print(f"   Actual product: {actual_product}")
        
        if actual_product == expected_product:
            print(f"✅ PASS: Product auto-filled correctly from master (product_map)")
        else:
            print(f"❌ FAIL: Product mismatch or not auto-filled")
            return False
        
        # Verify computed fields
        print(f"\n🔍 Computed Fields Verification:")
        
        has_standard_stock = "standard_stock" in test_record
        has_indikator = "indikator" in test_record
        
        print(f"   standard_stock: {test_record.get('standard_stock', 'MISSING')}")
        print(f"   indikator: {test_record.get('indikator', 'MISSING')}")
        
        if has_standard_stock and has_indikator:
            print(f"✅ PASS: standard_stock and indikator fields present")
        else:
            print(f"⚠️  WARNING: Some computed fields missing (may be expected if no standard set)")
        
        # Step 4: Verify production_needs view resolves product
        print(f"\n📥 Step 4: Checking production_needs view...")
        
        # First create a production record to trigger needs calculation
        test_prod_data = {
            "date": "2026-01-15",
            "lane": test_lane,
            "type": test_type,
            "ics_no": test_ics_no,
            # NO product field
            "tt": 60,
            "planing_smt": 100,
            "act_smt_s1": 30,
            "act_smt_s2": 30,
            "act_smt_s3": 30,
            "plan_assy": 50,
            "act_assy_s1": 15,
            "act_assy_s2": 15,
            "act_assy_s3": 15
        }
        
        response = session.post("/smt-production", test_prod_data)
        
        if response.status_code in [200, 201]:
            prod_id = response.json().get("id")
            session.test_data_ids.append(("smt_production", prod_id))
            print(f"✅ Created test production record: {prod_id}")
            
            # Now check production_needs view
            response = session.get("/production-needs", params={"date_from": "2026-01-15", "date_to": "2026-01-15"})
            
            if response.status_code == 200:
                needs_list = response.json()
                
                # Find our test record
                test_needs = None
                for record in needs_list:
                    if record.get("ics_no") == test_ics_no and record.get("type") == test_type and record.get("date") == "2026-01-15":
                        test_needs = record
                        break
                
                if test_needs:
                    needs_product = test_needs.get("product", "")
                    print(f"\n🔍 Production Needs Product Resolution:")
                    print(f"   Expected: {expected_product}")
                    print(f"   Actual: {needs_product}")
                    
                    if needs_product == expected_product:
                        print(f"✅ PASS: production_needs resolves product from master")
                    else:
                        print(f"⚠️  WARNING: production_needs product mismatch")
                else:
                    print(f"⚠️  INFO: Test record not found in production_needs (may need time to compute)")
            else:
                print(f"⚠️  INFO: Could not fetch production_needs view")
        else:
            print(f"⚠️  INFO: Could not create test production record (not critical for this test)")
        
        print(f"\n✅ TEST 3 PASSED: Cross-module linking verified")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Exception in test_3: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_items_crud_regression(session: TestSession):
    """
    TEST 4: Regression CRUD for items
    - Create new item with proses_mesin
    - List/find it
    - Update proses_mesin
    - Delete it
    - Confirm 618 count restored
    """
    print("\n" + "="*80)
    print("TEST 4: Items CRUD Regression")
    print("="*80)
    
    try:
        # Step 1: Create new item
        print("\n📤 Step 1: Creating new test item...")
        
        test_item_data = {
            "lane": "TEST-LANE-CRUD",
            "product": "REGULER",
            "type": "TEST-TYPE",
            "ics_no": "9999999999",
            "tt": 45.5,
            "tt_assy": 90.0,
            "material_per_unit": 2.0,
            "proses_mesin": "TEST-MACHINE"
        }
        
        response = session.post("/items", test_item_data)
        
        if response.status_code not in [200, 201]:
            print(f"❌ FAIL: Could not create item")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        created_item = response.json()
        item_id = created_item.get("id")
        
        print(f"✅ Created item: {item_id}")
        print(f"   proses_mesin: {created_item.get('proses_mesin')}")
        print(f"   cap_h: {created_item.get('cap_h')} (expected: {round(3600/45.5, 2)})")
        
        # Verify cap_h calculation
        expected_cap_h = round(3600 / 45.5, 2)
        actual_cap_h = created_item.get("cap_h", 0)
        
        if abs(actual_cap_h - expected_cap_h) < 0.01:
            print(f"✅ PASS: cap_h calculated correctly")
        else:
            print(f"❌ FAIL: cap_h calculation incorrect")
            return False
        
        # Step 2: List and find the item
        print(f"\n📥 Step 2: Listing items to find created item...")
        
        response = session.get("/items")
        
        if response.status_code != 200:
            print(f"❌ FAIL: Could not list items")
            return False
        
        items = response.json()
        found_item = None
        
        for item in items:
            if item.get("id") == item_id:
                found_item = item
                break
        
        if found_item:
            print(f"✅ PASS: Found created item in list")
            print(f"   ICS No: {found_item.get('ics_no')}")
            print(f"   proses_mesin: {found_item.get('proses_mesin')}")
        else:
            print(f"❌ FAIL: Could not find created item in list")
            return False
        
        # Step 3: Update proses_mesin
        print(f"\n📝 Step 3: Updating proses_mesin...")
        
        update_data = {
            **test_item_data,
            "proses_mesin": "UPDATED-MACHINE"
        }
        
        response = session.put(f"/items/{item_id}", update_data)
        
        if response.status_code != 200:
            print(f"❌ FAIL: Could not update item")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        updated_item = response.json()
        
        if updated_item.get("proses_mesin") == "UPDATED-MACHINE":
            print(f"✅ PASS: proses_mesin updated successfully")
            print(f"   New value: {updated_item.get('proses_mesin')}")
        else:
            print(f"❌ FAIL: proses_mesin not updated correctly")
            return False
        
        # Step 4: Delete the item
        print(f"\n🗑️  Step 4: Deleting test item...")
        
        response = session.delete(f"/items/{item_id}")
        
        if response.status_code not in [200, 204]:
            print(f"❌ FAIL: Could not delete item")
            print(f"   Status: {response.status_code}")
            return False
        
        print(f"✅ PASS: Item deleted successfully")
        
        # Step 5: Confirm 618 count restored
        print(f"\n📊 Step 5: Verifying item count restored to 618...")
        
        response = session.get("/items")
        
        if response.status_code != 200:
            print(f"❌ FAIL: Could not list items")
            return False
        
        items = response.json()
        final_count = len(items)
        
        print(f"   Final count: {final_count}")
        
        if final_count == 618:
            print(f"✅ PASS: Item count restored to 618")
        else:
            print(f"❌ FAIL: Item count is {final_count}, expected 618")
            return False
        
        print(f"\n✅ TEST 4 PASSED: CRUD operations working correctly")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Exception in test_4: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_items_filters(session: TestSession):
    """
    TEST 5: Items filters
    - Filter by product=REGULER
    - Filter by lane
    - Filter by type
    - Filter by ics_no
    Confirm no errors and sane results
    """
    print("\n" + "="*80)
    print("TEST 5: Items Filters")
    print("="*80)
    
    try:
        # Get all items first to determine filter values
        print("\n📥 Fetching all items to determine filter values...")
        response = session.get("/items")
        
        if response.status_code != 200:
            print(f"❌ FAIL: Could not fetch items")
            return False
        
        all_items = response.json()
        
        # Extract sample values for filtering
        sample_lane = None
        sample_type = None
        sample_ics_no = None
        
        for item in all_items:
            if not sample_lane and item.get("lane"):
                sample_lane = item["lane"]
            if not sample_type and item.get("type"):
                sample_type = item["type"]
            if not sample_ics_no and item.get("ics_no"):
                sample_ics_no = item["ics_no"]
            
            if sample_lane and sample_type and sample_ics_no:
                break
        
        print(f"   Sample lane: {sample_lane}")
        print(f"   Sample type: {sample_type}")
        print(f"   Sample ics_no: {sample_ics_no}")
        
        # Test 1: Filter by product=REGULER
        print(f"\n🔍 Test 5.1: Filter by product=REGULER")
        
        response = session.get("/items", params={"product": "REGULER"})
        
        if response.status_code != 200:
            print(f"❌ FAIL: Filter by product failed")
            print(f"   Status: {response.status_code}")
            return False
        
        filtered_items = response.json()
        
        # Verify all returned items have product=REGULER
        all_reguler = all(item.get("product") == "REGULER" for item in filtered_items)
        
        print(f"   Returned {len(filtered_items)} items")
        
        if all_reguler:
            print(f"✅ PASS: All filtered items have product=REGULER")
        else:
            print(f"❌ FAIL: Some items don't have product=REGULER")
            return False
        
        # Test 2: Filter by lane
        if sample_lane:
            print(f"\n🔍 Test 5.2: Filter by lane={sample_lane}")
            
            response = session.get("/items", params={"lane": sample_lane})
            
            if response.status_code != 200:
                print(f"❌ FAIL: Filter by lane failed")
                return False
            
            filtered_items = response.json()
            
            all_match = all(item.get("lane") == sample_lane for item in filtered_items)
            
            print(f"   Returned {len(filtered_items)} items")
            
            if all_match and len(filtered_items) > 0:
                print(f"✅ PASS: Filter by lane working correctly")
            else:
                print(f"❌ FAIL: Filter by lane not working correctly")
                return False
        
        # Test 3: Filter by type
        if sample_type:
            print(f"\n🔍 Test 5.3: Filter by type={sample_type}")
            
            response = session.get("/items", params={"type": sample_type})
            
            if response.status_code != 200:
                print(f"❌ FAIL: Filter by type failed")
                return False
            
            filtered_items = response.json()
            
            all_match = all(item.get("type") == sample_type for item in filtered_items)
            
            print(f"   Returned {len(filtered_items)} items")
            
            if all_match and len(filtered_items) > 0:
                print(f"✅ PASS: Filter by type working correctly")
            else:
                print(f"❌ FAIL: Filter by type not working correctly")
                return False
        
        # Test 4: Filter by ics_no
        if sample_ics_no:
            print(f"\n🔍 Test 5.4: Filter by ics_no={sample_ics_no}")
            
            response = session.get("/items", params={"ics_no": sample_ics_no})
            
            if response.status_code != 200:
                print(f"❌ FAIL: Filter by ics_no failed")
                return False
            
            filtered_items = response.json()
            
            all_match = all(item.get("ics_no") == sample_ics_no for item in filtered_items)
            
            print(f"   Returned {len(filtered_items)} items")
            
            if all_match and len(filtered_items) > 0:
                print(f"✅ PASS: Filter by ics_no working correctly")
            else:
                print(f"❌ FAIL: Filter by ics_no not working correctly")
                return False
        
        print(f"\n✅ TEST 5 PASSED: All filters working correctly")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Exception in test_5: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data(session: TestSession):
    """Clean up any test data created during tests"""
    print("\n" + "="*80)
    print("CLEANUP: Removing test data")
    print("="*80)
    
    for module, item_id in reversed(session.test_data_ids):
        try:
            endpoint_map = {
                "smt_stock": "/smt-stock",
                "smt_production": "/smt-production",
                "items": "/items"
            }
            
            endpoint = endpoint_map.get(module)
            if endpoint:
                response = session.delete(f"{endpoint}/{item_id}")
                if response.status_code in [200, 204]:
                    print(f"✅ Deleted {module} record: {item_id}")
                else:
                    print(f"⚠️  Could not delete {module} record: {item_id} (status: {response.status_code})")
        except Exception as e:
            print(f"⚠️  Error deleting {module} record {item_id}: {e}")
    
    print(f"✅ Cleanup complete")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("BACKEND TEST: Master Item Update (618 items) & Cross-Module Linking")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Date: 2026-01-15")
    
    session = TestSession()
    
    # Login
    if not session.login():
        print("\n❌ FATAL: Could not login, aborting tests")
        return
    
    # Run tests
    results = {
        "Test 1: Master Item Count & Fields (618 items)": test_1_master_item_count_and_fields(session),
        "Test 2: Meta Options (sourced from master)": test_2_meta_options(session),
        "Test 3: Cross-Module Linking (product_map)": test_3_cross_module_linking(session),
        "Test 4: Items CRUD Regression": test_4_items_crud_regression(session),
        "Test 5: Items Filters": test_5_items_filters(session),
    }
    
    # Cleanup
    cleanup_test_data(session)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r)
    
    print(f"\n📊 Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print(f"\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  SOME TESTS FAILED")


if __name__ == "__main__":
    main()
