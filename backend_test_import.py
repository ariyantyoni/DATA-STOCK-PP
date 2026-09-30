#!/usr/bin/env python3
"""
Backend Test: Master Item Schema Change - Import Test
Tests import functionality with new schema
"""

import requests
import json
import sys
from io import BytesIO
from openpyxl import Workbook

# Configuration
BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

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
    log("\n=== Authentication ===", Colors.BLUE)
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            log(f"✓ Login successful", Colors.GREEN)
            return token
        else:
            log(f"✗ Login failed: {response.status_code}", Colors.RED)
            return None
    except Exception as e:
        log(f"✗ Login error: {e}", Colors.RED)
        return None

def test_import_with_proses_mesin(token):
    """Test import functionality with proses_mesin field"""
    log("\n=== TEST: Import with proses_mesin ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create an Excel file with the new schema
    wb = Workbook()
    ws = wb.active
    ws.title = "Master Item"
    
    # Headers matching the new schema
    headers_row = ["Lane", "Product", "Type", "ICS No.", "T/T (detik)", 
                   "T/T Assy (detik/unit)", "Kebutuhan Material per Unit Assy", "PROSES MESIN"]
    ws.append(headers_row)
    
    # Test data row
    test_row = ["LT2", "REGULER", "IMPORT-TEST", "99999", 15, 6, 1, "LASER-01"]
    ws.append(test_row)
    
    # Save to BytesIO
    excel_buffer = BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    
    try:
        # Preview import
        log("Testing import preview...", Colors.YELLOW)
        files = {"file": ("test_import.xlsx", excel_buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = requests.post(
            f"{BASE_URL}/import/items/preview",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            preview_data = response.json()
            log(f"✓ Preview successful: {preview_data.get('total')} rows", Colors.GREEN)
            
            if preview_data.get('rows'):
                first_row = preview_data['rows'][0]
                
                # Check if proses_mesin is present
                if 'proses_mesin' in first_row and first_row['proses_mesin'] == 'LASER-01':
                    log(f"✓ proses_mesin field present in preview: {first_row['proses_mesin']}", Colors.GREEN)
                else:
                    log(f"✗ proses_mesin field missing or incorrect in preview", Colors.RED)
                    return None
                
                # Check if led_rank is NOT present
                if 'led_rank' in first_row:
                    log(f"✗ led_rank field should NOT be present in preview", Colors.RED)
                else:
                    log("✓ led_rank field correctly absent in preview", Colors.GREEN)
        else:
            log(f"✗ Preview failed: {response.status_code} - {response.text}", Colors.RED)
            return None
        
        # Confirm import
        log("Confirming import...", Colors.YELLOW)
        excel_buffer.seek(0)
        files = {"file": ("test_import.xlsx", excel_buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = requests.post(
            f"{BASE_URL}/import/items/confirm",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            import_result = response.json()
            log(f"✓ Import successful: {import_result.get('inserted')} inserted, {import_result.get('updated')} updated", Colors.GREEN)
            
            # Verify the imported item
            response = requests.get(
                f"{BASE_URL}/items?ics_no=99999",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                items = response.json()
                if items:
                    imported_item = items[0]
                    item_id = imported_item.get("id")
                    
                    if imported_item.get("proses_mesin") == "LASER-01":
                        log(f"✓ Imported item has proses_mesin: {imported_item['proses_mesin']}", Colors.GREEN)
                    else:
                        log(f"✗ Imported item proses_mesin incorrect: {imported_item.get('proses_mesin')}", Colors.RED)
                    
                    if "led_rank" in imported_item:
                        log(f"✗ Imported item should NOT have led_rank", Colors.RED)
                    else:
                        log("✓ Imported item correctly has no led_rank", Colors.GREEN)
                    
                    return item_id
                else:
                    log("✗ Imported item not found", Colors.RED)
                    return None
            else:
                log(f"✗ Failed to retrieve imported item: {response.status_code}", Colors.RED)
                return None
        else:
            log(f"✗ Import failed: {response.status_code} - {response.text}", Colors.RED)
            return None
            
    except Exception as e:
        log(f"✗ Import error: {e}", Colors.RED)
        return None

def cleanup_test_item(token, ics_no="99999"):
    """Delete test item by ICS number"""
    log("\n=== Cleanup Test Item ===", Colors.BLUE)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Find the item
        response = requests.get(
            f"{BASE_URL}/items?ics_no={ics_no}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            items = response.json()
            if items:
                item_id = items[0].get("id")
                
                # Delete it
                response = requests.delete(
                    f"{BASE_URL}/items/{item_id}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    log(f"✓ Test item deleted", Colors.GREEN)
                    return True
                else:
                    log(f"✗ Delete failed: {response.status_code}", Colors.RED)
                    return False
            else:
                log("ℹ No test item to delete", Colors.YELLOW)
                return True
        else:
            log(f"✗ Failed to find test item: {response.status_code}", Colors.RED)
            return False
    except Exception as e:
        log(f"✗ Cleanup error: {e}", Colors.RED)
        return False

def main():
    log("=" * 70, Colors.BLUE)
    log("BACKEND TEST: Master Item Import with New Schema", Colors.BLUE)
    log("=" * 70, Colors.BLUE)
    
    # Login
    token = login()
    if not token:
        log("\n✗ FAILED: Cannot proceed without authentication", Colors.RED)
        sys.exit(1)
    
    # Test import
    item_id = test_import_with_proses_mesin(token)
    
    # Cleanup
    cleanup_test_item(token)
    
    log("\n" + "=" * 70, Colors.BLUE)
    if item_id:
        log("TEST PASSED", Colors.GREEN)
    else:
        log("TEST FAILED", Colors.RED)
    log("=" * 70, Colors.BLUE)

if __name__ == "__main__":
    main()
