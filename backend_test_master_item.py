#!/usr/bin/env python3
"""
Backend Test: Master Item Schema Change
Tests the removal of "led_rank" field and addition of "proses_mesin" field
"""

import requests
import json
import sys
from io import BytesIO
from openpyxl import load_workbook

# Configuration
BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Test data
TEST_ITEM = {
    "lane": "LT1",
    "product": "REGULER",
    "type": "QATEST",
    "ics_no": "12345",
    "tt": 12,
    "tt_assy": 5,
    "material_per_unit": 1,
    "proses_mesin": "CNC-01"
}

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log(msg, color=None):
    if color:
        print(f"{color}{msg}{Colors.END}")
    else:
        print(msg)

def login():
    """Login and get auth token"""
    log("\n=== TEST 1: Authentication ===", Colors.BLUE)
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            log(f"✓ Login successful as {ADMIN_USERNAME}", Colors.GREEN)
            return token
        else:
            log(f"✗ Login failed: {response.status_code} - {response.text}", Colors.RED)
            return None
    except Exception as e:
        log(f"✗ Login error: {e}", Colors.RED)
        return None

def test_create_item(token):
    """Test 1: CREATE a master item with proses_mesin field"""
    log("\n=== TEST 2: CREATE Master Item with proses_mesin ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(
            f"{BASE_URL}/items",
            json=TEST_ITEM,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            item_id = data.get("id")
            
            # Verify proses_mesin is present
            if "proses_mesin" in data and data["proses_mesin"] == "CNC-01":
                log(f"✓ proses_mesin field present: {data['proses_mesin']}", Colors.GREEN)
            else:
                log(f"✗ proses_mesin field missing or incorrect: {data.get('proses_mesin')}", Colors.RED)
                return None
            
            # Verify led_rank is NOT present
            if "led_rank" in data:
                log(f"✗ led_rank field should NOT be present but found: {data['led_rank']}", Colors.RED)
                return None
            else:
                log("✓ led_rank field correctly absent", Colors.GREEN)
            
            # Verify cap_h is computed
            if "cap_h" in data:
                expected_cap_h = round(3600 / TEST_ITEM["tt"], 2)
                actual_cap_h = data["cap_h"]
                if actual_cap_h == expected_cap_h:
                    log(f"✓ cap_h computed correctly: {actual_cap_h} (expected: {expected_cap_h})", Colors.GREEN)
                else:
                    log(f"✗ cap_h incorrect: {actual_cap_h} (expected: {expected_cap_h})", Colors.RED)
            else:
                log("✗ cap_h field missing", Colors.RED)
            
            log(f"✓ Item created successfully with ID: {item_id}", Colors.GREEN)
            return item_id
        else:
            log(f"✗ Create failed: {response.status_code} - {response.text}", Colors.RED)
            return None
    except Exception as e:
        log(f"✗ Create error: {e}", Colors.RED)
        return None

def test_get_items(token, item_id):
    """Test 2: GET /api/items list and verify the created item"""
    log("\n=== TEST 3: GET Items List ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/items",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            items = response.json()
            log(f"✓ Retrieved {len(items)} items", Colors.GREEN)
            
            # Find our test item
            test_item = None
            for item in items:
                if item.get("id") == item_id:
                    test_item = item
                    break
            
            if test_item:
                log(f"✓ Test item found in list", Colors.GREEN)
                
                # Verify proses_mesin
                if test_item.get("proses_mesin") == "CNC-01":
                    log(f"✓ proses_mesin field present: {test_item['proses_mesin']}", Colors.GREEN)
                else:
                    log(f"✗ proses_mesin field incorrect: {test_item.get('proses_mesin')}", Colors.RED)
                
                # Verify led_rank is NOT present
                if "led_rank" in test_item:
                    log(f"✗ led_rank field should NOT be present", Colors.RED)
                else:
                    log("✓ led_rank field correctly absent", Colors.GREEN)
                
                return True
            else:
                log(f"✗ Test item not found in list", Colors.RED)
                return False
        else:
            log(f"✗ GET items failed: {response.status_code} - {response.text}", Colors.RED)
            return False
    except Exception as e:
        log(f"✗ GET items error: {e}", Colors.RED)
        return False

def test_update_item(token, item_id):
    """Test 3: UPDATE the item changing proses_mesin"""
    log("\n=== TEST 4: UPDATE Item proses_mesin ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    update_data = {
        **TEST_ITEM,
        "proses_mesin": "CNC-02"
    }
    
    try:
        response = requests.put(
            f"{BASE_URL}/items/{item_id}",
            json=update_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("proses_mesin") == "CNC-02":
                log(f"✓ proses_mesin updated successfully: {data['proses_mesin']}", Colors.GREEN)
                return True
            else:
                log(f"✗ proses_mesin not updated: {data.get('proses_mesin')}", Colors.RED)
                return False
        else:
            log(f"✗ Update failed: {response.status_code} - {response.text}", Colors.RED)
            return False
    except Exception as e:
        log(f"✗ Update error: {e}", Colors.RED)
        return False

def test_import_template(token):
    """Test 4: Download import template and verify column headers"""
    log("\n=== TEST 5: Import Template Column Headers ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/import/items/template",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            log("✓ Template downloaded successfully", Colors.GREEN)
            
            # Load the Excel file
            wb = load_workbook(BytesIO(response.content))
            ws = wb.active
            
            # Get headers from first row
            headers_row = [cell.value for cell in ws[1]]
            log(f"Column headers: {headers_row}", Colors.YELLOW)
            
            # Verify "PROSES MESIN" is present
            if "PROSES MESIN" in headers_row:
                log("✓ 'PROSES MESIN' column header present", Colors.GREEN)
            else:
                log("✗ 'PROSES MESIN' column header missing", Colors.RED)
                return False
            
            # Verify "LED Rank" is NOT present
            if "LED Rank" in headers_row or "LED RANK" in headers_row:
                log("✗ 'LED Rank' column header should NOT be present", Colors.RED)
                return False
            else:
                log("✓ 'LED Rank' column header correctly absent", Colors.GREEN)
            
            # Verify expected columns
            expected_columns = ["Lane", "Product", "Type", "ICS No.", "T/T (detik)", 
                              "T/T Assy (detik/unit)", "Kebutuhan Material per Unit Assy", "PROSES MESIN"]
            
            all_present = True
            for col in expected_columns:
                if col not in headers_row:
                    log(f"✗ Expected column missing: {col}", Colors.RED)
                    all_present = False
            
            if all_present:
                log("✓ All expected columns present", Colors.GREEN)
            
            return all_present
        else:
            log(f"✗ Template download failed: {response.status_code} - {response.text}", Colors.RED)
            return False
    except Exception as e:
        log(f"✗ Template download error: {e}", Colors.RED)
        return False

def test_delete_item(token, item_id):
    """Test 5: DELETE the test item"""
    log("\n=== TEST 6: DELETE Test Item ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.delete(
            f"{BASE_URL}/items/{item_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            log(f"✓ Test item deleted successfully", Colors.GREEN)
            return True
        else:
            log(f"✗ Delete failed: {response.status_code} - {response.text}", Colors.RED)
            return False
    except Exception as e:
        log(f"✗ Delete error: {e}", Colors.RED)
        return False

def test_verify_base_items(token):
    """Test 6: Verify 119 pre-existing items still work"""
    log("\n=== TEST 7: Verify Base Items (119 expected) ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/items",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            items = response.json()
            count = len(items)
            
            if count == 119:
                log(f"✓ Item count correct: {count} items (expected 119)", Colors.GREEN)
            else:
                log(f"⚠ Item count: {count} items (expected 119)", Colors.YELLOW)
            
            # Check that pre-existing items don't have led_rank
            items_with_led_rank = [item for item in items if "led_rank" in item]
            if items_with_led_rank:
                log(f"✗ Found {len(items_with_led_rank)} items with led_rank field", Colors.RED)
                return False
            else:
                log("✓ No items have led_rank field", Colors.GREEN)
            
            # Check that items may or may not have proses_mesin (acceptable for old items)
            items_with_proses = [item for item in items if item.get("proses_mesin")]
            log(f"ℹ {len(items_with_proses)} items have proses_mesin populated", Colors.YELLOW)
            
            return count == 119
        else:
            log(f"✗ GET items failed: {response.status_code} - {response.text}", Colors.RED)
            return False
    except Exception as e:
        log(f"✗ GET items error: {e}", Colors.RED)
        return False

def main():
    log("=" * 70, Colors.BLUE)
    log("BACKEND TEST: Master Item Schema Change", Colors.BLUE)
    log("Testing: led_rank removed, proses_mesin added", Colors.BLUE)
    log("=" * 70, Colors.BLUE)
    
    # Login
    token = login()
    if not token:
        log("\n✗ FAILED: Cannot proceed without authentication", Colors.RED)
        sys.exit(1)
    
    # Test 1: Create item with proses_mesin
    item_id = test_create_item(token)
    if not item_id:
        log("\n✗ FAILED: Cannot proceed without creating test item", Colors.RED)
        sys.exit(1)
    
    # Test 2: Get items list
    if not test_get_items(token, item_id):
        log("\n⚠ WARNING: GET items test failed", Colors.YELLOW)
    
    # Test 3: Update item
    if not test_update_item(token, item_id):
        log("\n⚠ WARNING: UPDATE item test failed", Colors.YELLOW)
    
    # Test 4: Import template
    if not test_import_template(token):
        log("\n⚠ WARNING: Import template test failed", Colors.YELLOW)
    
    # Test 5: Delete test item
    if not test_delete_item(token, item_id):
        log("\n⚠ WARNING: DELETE item test failed (cleanup incomplete)", Colors.YELLOW)
    
    # Test 6: Verify base items
    if not test_verify_base_items(token):
        log("\n⚠ WARNING: Base items verification failed", Colors.YELLOW)
    
    log("\n" + "=" * 70, Colors.BLUE)
    log("TEST SUITE COMPLETED", Colors.GREEN)
    log("=" * 70, Colors.BLUE)

if __name__ == "__main__":
    main()
