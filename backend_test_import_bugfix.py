#!/usr/bin/env python3
"""
Test script for IMPORT BUGFIX verification - Master Item & Standar Stock modules
Tests the fixes for:
1. stock-standards preview wrongly counting rows as invalid (required ics_no but key is lane+product+type)
2. Missing header aliases for "T/T Assy (dtk/unit)", "Material / Unit Assy"
"""

import requests
import csv
import io
import os
from openpyxl import Workbook

# Base URL from frontend/.env
BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
USERNAME = "admin"
PASSWORD = "admin123"

# Global session with auth token
session = requests.Session()

def login():
    """Login and get auth token"""
    print("\n=== LOGIN ===")
    resp = session.post(f"{BASE_URL}/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token")
    assert token, "No token in login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"✓ Logged in as {data['user']['username']}")
    return data["user"]

def create_csv_file(headers, rows):
    """Create CSV file in memory"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return output.getvalue().encode('utf-8')

def create_xlsx_file(headers, rows):
    """Create XLSX file in memory"""
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

def import_preview(dataset, file_content, filename):
    """POST /api/import/{dataset}/preview"""
    files = {"file": (filename, file_content, "application/octet-stream")}
    resp = session.post(f"{BASE_URL}/import/{dataset}/preview", files=files)
    assert resp.status_code == 200, f"Preview failed: {resp.status_code} {resp.text}"
    return resp.json()

def import_confirm(dataset, file_content, filename):
    """POST /api/import/{dataset}/confirm"""
    files = {"file": (filename, file_content, "application/octet-stream")}
    resp = session.post(f"{BASE_URL}/import/{dataset}/confirm", files=files)
    assert resp.status_code == 200, f"Confirm failed: {resp.status_code} {resp.text}"
    return resp.json()

def get_items(type_filter=None):
    """GET /api/items with optional type filter"""
    params = {"type": type_filter} if type_filter else {}
    resp = session.get(f"{BASE_URL}/items", params=params)
    assert resp.status_code == 200, f"Get items failed: {resp.status_code} {resp.text}"
    return resp.json()

def delete_item(item_id):
    """DELETE /api/items/{id}"""
    resp = session.delete(f"{BASE_URL}/items/{item_id}")
    assert resp.status_code == 200, f"Delete item failed: {resp.status_code} {resp.text}"
    return resp.json()

def get_stock_standards(type_filter=None):
    """GET /api/stock-standards with optional type filter"""
    params = {"type": type_filter} if type_filter else {}
    resp = session.get(f"{BASE_URL}/stock-standards", params=params)
    assert resp.status_code == 200, f"Get stock-standards failed: {resp.status_code} {resp.text}"
    return resp.json()

def delete_stock_standard(std_id):
    """DELETE /api/stock-standards/{id}"""
    resp = session.delete(f"{BASE_URL}/stock-standards/{std_id}")
    assert resp.status_code == 200, f"Delete stock-standard failed: {resp.status_code} {resp.text}"
    return resp.json()

def get_smt_stock(type_filter=None):
    """GET /api/smt-stock with optional type filter"""
    params = {"type": type_filter} if type_filter else {}
    resp = session.get(f"{BASE_URL}/smt-stock", params=params)
    assert resp.status_code == 200, f"Get smt-stock failed: {resp.status_code} {resp.text}"
    return resp.json()

def delete_smt_stock(stock_id):
    """DELETE /api/smt-stock/{id}"""
    resp = session.delete(f"{BASE_URL}/smt-stock/{stock_id}")
    assert resp.status_code == 200, f"Delete smt-stock failed: {resp.status_code} {resp.text}"
    return resp.json()

def test_1_stock_standards():
    """
    TEST 1: STOCK-STANDARDS (dataset "stock-standards")
    - Build CSV with header: Lane,Product,Type,Standart Stock and 2 data rows (Type ZZZSTD1, ZZZSTD2)
    - POST preview → EXPECT invalid=0 and new=2 (NOT 0)
    - POST confirm → EXPECT inserted=2
    - POST confirm again with SAME file → EXPECT updated=2 (duplicates updated, NOT inserted again)
    - Verify records exist, then DELETE them
    """
    print("\n" + "="*80)
    print("TEST 1: STOCK-STANDARDS IMPORT")
    print("="*80)
    
    # Create CSV file
    headers = ["Lane", "Product", "Type", "Standart Stock"]
    rows = [
        ["PM 01", "REGULER", "ZZZSTD1", "100"],
        ["PM 02", "SPO", "ZZZSTD2", "200"]
    ]
    csv_content = create_csv_file(headers, rows)
    
    # Preview
    print("\n--- Preview Import ---")
    preview = import_preview("stock-standards", csv_content, "test_stock_standards.csv")
    print(f"Preview result: {preview}")
    
    # Verify preview counts
    assert preview["invalid"] == 0, f"Expected invalid=0, got {preview['invalid']}"
    assert preview["new"] == 2, f"Expected new=2, got {preview['new']}"
    print(f"✓ Preview PASS: invalid={preview['invalid']}, new={preview['new']}")
    
    # Confirm import (first time)
    print("\n--- Confirm Import (First Time) ---")
    confirm1 = import_confirm("stock-standards", csv_content, "test_stock_standards.csv")
    print(f"Confirm result: {confirm1}")
    assert confirm1["inserted"] == 2, f"Expected inserted=2, got {confirm1['inserted']}"
    print(f"✓ First import PASS: inserted={confirm1['inserted']}")
    
    # Confirm import (second time - should update, not insert)
    print("\n--- Confirm Import (Second Time - Duplicate Check) ---")
    confirm2 = import_confirm("stock-standards", csv_content, "test_stock_standards.csv")
    print(f"Confirm result: {confirm2}")
    assert confirm2["updated"] == 2, f"Expected updated=2, got {confirm2['updated']}"
    assert confirm2["inserted"] == 0, f"Expected inserted=0 (duplicates), got {confirm2['inserted']}"
    print(f"✓ Duplicate handling PASS: updated={confirm2['updated']}, inserted={confirm2['inserted']}")
    
    # Verify records exist
    print("\n--- Verify Records Exist ---")
    std1 = get_stock_standards("ZZZSTD1")
    std2 = get_stock_standards("ZZZSTD2")
    assert len(std1) == 1, f"Expected 1 record for ZZZSTD1, got {len(std1)}"
    assert len(std2) == 1, f"Expected 1 record for ZZZSTD2, got {len(std2)}"
    print(f"✓ Records found: ZZZSTD1 (id={std1[0]['id']}), ZZZSTD2 (id={std2[0]['id']})")
    
    # Delete test data
    print("\n--- Cleanup Test Data ---")
    delete_stock_standard(std1[0]["id"])
    delete_stock_standard(std2[0]["id"])
    print("✓ Test data deleted")
    
    print("\n✅ TEST 1 PASSED: Stock-standards import working correctly")

def test_2_items_attachment_header():
    """
    TEST 2: ITEMS with ATTACHMENT-style header
    - Build CSV header: Lane,Product,Type,ICS No.,T/T (detik),T/T Assy (dtk/unit),Kebutuhan Material per Unit Assy,PROSES MESIN
    - 1 row: Type ZZZITEM, ICS No. 1234500099, T/T 20, T/T Assy 10, material 1, PROSES MESIN INJECTION
    - POST preview → EXPECT unknown_columns EMPTY and parsed row tt_assy=10 (NOT 0), proses_mesin="INJECTION", cap_h=180
    - POST confirm → inserted=1
    - Verify via GET /api/items?type=ZZZITEM that tt_assy=10 and proses_mesin=INJECTION
    - DELETE and confirm items count returns to 618
    """
    print("\n" + "="*80)
    print("TEST 2: ITEMS IMPORT WITH ATTACHMENT-STYLE HEADER")
    print("="*80)
    
    # Get initial item count
    print("\n--- Get Initial Item Count ---")
    initial_items = get_items()
    initial_count = len(initial_items)
    print(f"Initial item count: {initial_count}")
    
    # Create CSV file with attachment-style header
    headers = ["Lane", "Product", "Type", "ICS No.", "T/T (detik)", "T/T Assy (dtk/unit)", "Kebutuhan Material per Unit Assy", "PROSES MESIN"]
    rows = [
        ["PM 99", "REGULER", "ZZZITEM", "1234500099", "20", "10", "1", "INJECTION"]
    ]
    csv_content = create_csv_file(headers, rows)
    
    # Preview
    print("\n--- Preview Import ---")
    preview = import_preview("items", csv_content, "test_items_attachment.csv")
    print(f"Preview result: {preview}")
    
    # Verify preview
    assert len(preview["unknown_columns"]) == 0, f"Expected unknown_columns=[], got {preview['unknown_columns']}"
    assert preview["new"] == 1, f"Expected new=1, got {preview['new']}"
    
    # Check parsed row
    row = preview["rows"][0]
    assert row["tt_assy"] == 10.0, f"Expected tt_assy=10, got {row['tt_assy']}"
    assert row["proses_mesin"] == "INJECTION", f"Expected proses_mesin='INJECTION', got {row['proses_mesin']}"
    assert row["cap_h"] == 180.0, f"Expected cap_h=180 (3600/20), got {row['cap_h']}"
    print(f"✓ Preview PASS: unknown_columns={preview['unknown_columns']}, tt_assy={row['tt_assy']}, proses_mesin={row['proses_mesin']}, cap_h={row['cap_h']}")
    
    # Confirm import
    print("\n--- Confirm Import ---")
    confirm = import_confirm("items", csv_content, "test_items_attachment.csv")
    print(f"Confirm result: {confirm}")
    assert confirm["inserted"] == 1, f"Expected inserted=1, got {confirm['inserted']}"
    print(f"✓ Import PASS: inserted={confirm['inserted']}")
    
    # Verify via GET
    print("\n--- Verify via GET /api/items?type=ZZZITEM ---")
    items = get_items("ZZZITEM")
    assert len(items) == 1, f"Expected 1 item, got {len(items)}"
    item = items[0]
    assert item["tt_assy"] == 10.0, f"Expected tt_assy=10, got {item['tt_assy']}"
    assert item["proses_mesin"] == "INJECTION", f"Expected proses_mesin='INJECTION', got {item['proses_mesin']}"
    print(f"✓ Item verified: tt_assy={item['tt_assy']}, proses_mesin={item['proses_mesin']}")
    
    # Delete test data
    print("\n--- Delete Test Data ---")
    delete_item(item["id"])
    print("✓ Test data deleted")
    
    # Verify count returns to initial
    print("\n--- Verify Item Count ---")
    final_items = get_items()
    final_count = len(final_items)
    assert final_count == initial_count, f"Expected count={initial_count}, got {final_count}"
    print(f"✓ Item count restored to {final_count}")
    
    print("\n✅ TEST 2 PASSED: Items import with attachment-style header working correctly")

def test_3_roundtrip_frontend_export():
    """
    TEST 3: ROUNDTRIP with FRONTEND EXPORT labels
    - items header: Lane,Product,Type,ICS No.,T/T (detik),CAP/H,T/T Assy (dtk/unit),Proses Mesin,Material / Unit Assy
    - 1 row, Type ZZZEXP
    - preview → unknown_columns should be ["CAP/H"] only (CAP/H intentionally skipped) OR empty
    - tt_assy and material_per_unit must be mapped (non-zero)
    - confirm inserted=1, then delete
    """
    print("\n" + "="*80)
    print("TEST 3: ROUNDTRIP WITH FRONTEND EXPORT LABELS")
    print("="*80)
    
    # Create CSV file with frontend export labels
    headers = ["Lane", "Product", "Type", "ICS No.", "T/T (detik)", "CAP/H", "T/T Assy (dtk/unit)", "Proses Mesin", "Material / Unit Assy"]
    rows = [
        ["PM 88", "SPO", "ZZZEXP", "9999900001", "30", "120", "15", "VAKUM", "2"]
    ]
    csv_content = create_csv_file(headers, rows)
    
    # Preview
    print("\n--- Preview Import ---")
    preview = import_preview("items", csv_content, "test_items_roundtrip.csv")
    print(f"Preview result: {preview}")
    
    # Verify preview
    # CAP/H should be in unknown_columns or skipped (it's computed, not stored)
    unknown = preview["unknown_columns"]
    print(f"Unknown columns: {unknown}")
    # CAP/H is marked as __skip__ in header_map, so it should NOT appear in unknown_columns
    # It should be silently skipped
    assert "CAP/H" not in unknown or len(unknown) <= 1, f"Unexpected unknown_columns: {unknown}"
    
    # Check parsed row
    row = preview["rows"][0]
    assert row["tt_assy"] == 15.0, f"Expected tt_assy=15, got {row['tt_assy']}"
    assert row["material_per_unit"] == 2.0, f"Expected material_per_unit=2, got {row['material_per_unit']}"
    assert row["proses_mesin"] == "VAKUM", f"Expected proses_mesin='VAKUM', got {row['proses_mesin']}"
    print(f"✓ Preview PASS: tt_assy={row['tt_assy']}, material_per_unit={row['material_per_unit']}, proses_mesin={row['proses_mesin']}")
    
    # Confirm import
    print("\n--- Confirm Import ---")
    confirm = import_confirm("items", csv_content, "test_items_roundtrip.csv")
    print(f"Confirm result: {confirm}")
    assert confirm["inserted"] == 1, f"Expected inserted=1, got {confirm['inserted']}"
    print(f"✓ Import PASS: inserted={confirm['inserted']}")
    
    # Verify and delete
    print("\n--- Verify and Delete ---")
    items = get_items("ZZZEXP")
    assert len(items) == 1, f"Expected 1 item, got {len(items)}"
    delete_item(items[0]["id"])
    print("✓ Test data deleted")
    
    print("\n✅ TEST 3 PASSED: Roundtrip with frontend export labels working correctly")

def test_4_xlsx_import():
    """
    TEST 4: XLSX import
    - Repeat minimal items import using .xlsx file (not csv)
    - Insert 1 row (Type ZZZXLSX)
    - Verify, delete
    """
    print("\n" + "="*80)
    print("TEST 4: XLSX IMPORT")
    print("="*80)
    
    # Create XLSX file
    headers = ["Lane", "Product", "Type", "ICS No.", "T/T (detik)", "T/T Assy (dtk/unit)", "Kebutuhan Material per Unit Assy", "PROSES MESIN"]
    rows = [
        ["PM 77", "REGULER", "ZZZXLSX", "8888800001", "25", "12", "1.5", "PAINTING"]
    ]
    xlsx_content = create_xlsx_file(headers, rows)
    
    # Preview
    print("\n--- Preview Import (XLSX) ---")
    preview = import_preview("items", xlsx_content, "test_items.xlsx")
    print(f"Preview result: {preview}")
    assert preview["new"] == 1, f"Expected new=1, got {preview['new']}"
    print(f"✓ Preview PASS: new={preview['new']}")
    
    # Confirm import
    print("\n--- Confirm Import (XLSX) ---")
    confirm = import_confirm("items", xlsx_content, "test_items.xlsx")
    print(f"Confirm result: {confirm}")
    assert confirm["inserted"] == 1, f"Expected inserted=1, got {confirm['inserted']}"
    print(f"✓ Import PASS: inserted={confirm['inserted']}")
    
    # Verify and delete
    print("\n--- Verify and Delete ---")
    items = get_items("ZZZXLSX")
    assert len(items) == 1, f"Expected 1 item, got {len(items)}"
    item = items[0]
    assert item["proses_mesin"] == "PAINTING", f"Expected proses_mesin='PAINTING', got {item['proses_mesin']}"
    print(f"✓ Item verified: proses_mesin={item['proses_mesin']}")
    delete_item(item["id"])
    print("✓ Test data deleted")
    
    print("\n✅ TEST 4 PASSED: XLSX import working correctly")

def test_5_regression_transaction_import():
    """
    TEST 5: REGRESSION - transaction import still works
    - dataset "smt-stock" with header including Tanggal + ICS No. + Type + stock columns
    - 1 row (Type ZZZTRX, valid date)
    - preview invalid=0/new=1
    - confirm inserted=1
    - delete
    """
    print("\n" + "="*80)
    print("TEST 5: REGRESSION - TRANSACTION IMPORT (smt-stock)")
    print("="*80)
    
    # Create CSV file for smt-stock
    headers = ["Tanggal", "Lane", "Product", "Type", "ICS No.", "Stock OK Part Kemarin", "Coating", "Belum Cutting", "Belum ICT", "Belum FCT", "OK"]
    rows = [
        ["2025-01-15", "PM 66", "REGULER", "ZZZTRX", "7777700001", "50", "10", "5", "3", "2", "30"]
    ]
    csv_content = create_csv_file(headers, rows)
    
    # Preview
    print("\n--- Preview Import ---")
    preview = import_preview("smt-stock", csv_content, "test_smt_stock.csv")
    print(f"Preview result: {preview}")
    assert preview["invalid"] == 0, f"Expected invalid=0, got {preview['invalid']}"
    assert preview["new"] == 1, f"Expected new=1, got {preview['new']}"
    print(f"✓ Preview PASS: invalid={preview['invalid']}, new={preview['new']}")
    
    # Confirm import
    print("\n--- Confirm Import ---")
    confirm = import_confirm("smt-stock", csv_content, "test_smt_stock.csv")
    print(f"Confirm result: {confirm}")
    assert confirm["inserted"] == 1, f"Expected inserted=1, got {confirm['inserted']}"
    print(f"✓ Import PASS: inserted={confirm['inserted']}")
    
    # Verify and delete
    print("\n--- Verify and Delete ---")
    stocks = get_smt_stock("ZZZTRX")
    assert len(stocks) == 1, f"Expected 1 stock record, got {len(stocks)}"
    delete_smt_stock(stocks[0]["id"])
    print("✓ Test data deleted")
    
    print("\n✅ TEST 5 PASSED: Transaction import (smt-stock) still working correctly")

def verify_final_state():
    """Verify final state: item count should be 618, all ZZZ test data removed"""
    print("\n" + "="*80)
    print("FINAL STATE VERIFICATION")
    print("="*80)
    
    # Check item count
    print("\n--- Verify Item Count ---")
    items = get_items()
    item_count = len(items)
    print(f"Final item count: {item_count}")
    assert item_count == 618, f"Expected 618 items, got {item_count}"
    print(f"✓ Item count correct: {item_count}")
    
    # Check for any remaining ZZZ test data
    print("\n--- Check for Remaining ZZZ Test Data ---")
    zzz_items = [item for item in items if "ZZZ" in item.get("type", "")]
    if zzz_items:
        print(f"⚠️ WARNING: Found {len(zzz_items)} items with ZZZ in type:")
        for item in zzz_items:
            print(f"  - {item['type']} (id={item['id']})")
            # Clean up
            delete_item(item["id"])
            print(f"    Deleted")
    else:
        print("✓ No ZZZ test data found in items")
    
    # Check stock-standards
    standards = get_stock_standards()
    zzz_standards = [std for std in standards if "ZZZ" in std.get("type", "")]
    if zzz_standards:
        print(f"⚠️ WARNING: Found {len(zzz_standards)} stock-standards with ZZZ in type:")
        for std in zzz_standards:
            print(f"  - {std['type']} (id={std['id']})")
            delete_stock_standard(std["id"])
            print(f"    Deleted")
    else:
        print("✓ No ZZZ test data found in stock-standards")
    
    # Check smt-stock
    stocks = get_smt_stock()
    zzz_stocks = [stock for stock in stocks if "ZZZ" in stock.get("type", "")]
    if zzz_stocks:
        print(f"⚠️ WARNING: Found {len(zzz_stocks)} smt-stock records with ZZZ in type:")
        for stock in zzz_stocks:
            print(f"  - {stock['type']} (id={stock['id']})")
            delete_smt_stock(stock["id"])
            print(f"    Deleted")
    else:
        print("✓ No ZZZ test data found in smt-stock")
    
    print("\n✅ FINAL STATE VERIFIED: All test data cleaned up, item count = 618")

def main():
    """Run all tests"""
    print("="*80)
    print("IMPORT BUGFIX VERIFICATION TEST SUITE")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Username: {USERNAME}")
    
    try:
        # Login
        user = login()
        
        # Run all tests
        test_1_stock_standards()
        test_2_items_attachment_header()
        test_3_roundtrip_frontend_export()
        test_4_xlsx_import()
        test_5_regression_transaction_import()
        
        # Verify final state
        verify_final_state()
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED")
        print("="*80)
        print("\nSUMMARY:")
        print("✅ TEST 1: Stock-standards import (preview invalid=0, new=2, duplicate handling)")
        print("✅ TEST 2: Items import with attachment-style header (tt_assy, proses_mesin mapped)")
        print("✅ TEST 3: Roundtrip with frontend export labels (CAP/H skipped, fields mapped)")
        print("✅ TEST 4: XLSX import (openpyxl parsing working)")
        print("✅ TEST 5: Regression - transaction import (smt-stock still working)")
        print("✅ FINAL: All ZZZ test data cleaned up, item count = 618")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise

if __name__ == "__main__":
    main()
