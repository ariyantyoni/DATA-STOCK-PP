#!/usr/bin/env python3
"""
Comprehensive Dashboard Summary Endpoint Test
Tests the NEW Dashboard summary endpoint logic on PART PRODUCTION backend.
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://data-stock-branch.preview.emergentagent.com/api"
USERNAME = "admin"
PASSWORD = "admin123"

# Test results tracking
test_results = []
created_ids = {"production": [], "stock": []}

def log_result(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"test": test_name, "passed": passed, "details": details})
    print(f"{status}: {test_name}")
    if details:
        print(f"   {details}")

def login():
    """Login and get token"""
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.status_code} {resp.text}")
    return resp.json()["token"]

def get_headers(token):
    """Get request headers with auth"""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def create_production_record(token, data):
    """Create a production record and track its ID"""
    headers = get_headers(token)
    resp = requests.post(f"{BASE_URL}/smt-production", json=data, headers=headers)
    if resp.status_code == 200:
        record_id = resp.json().get("id")
        created_ids["production"].append(record_id)
        return record_id
    else:
        raise Exception(f"Failed to create production record: {resp.status_code} {resp.text}")

def create_stock_record(token, data):
    """Create a stock record and track its ID"""
    headers = get_headers(token)
    resp = requests.post(f"{BASE_URL}/smt-stock", json=data, headers=headers)
    if resp.status_code == 200:
        record_id = resp.json().get("id")
        created_ids["stock"].append(record_id)
        return record_id
    else:
        raise Exception(f"Failed to create stock record: {resp.status_code} {resp.text}")

def cleanup_test_data(token):
    """Delete all created test data"""
    headers = get_headers(token)
    deleted_count = 0
    
    # Delete production records
    for record_id in created_ids["production"]:
        resp = requests.delete(f"{BASE_URL}/smt-production/{record_id}", headers=headers)
        if resp.status_code == 200:
            deleted_count += 1
    
    # Delete stock records
    for record_id in created_ids["stock"]:
        resp = requests.delete(f"{BASE_URL}/smt-stock/{record_id}", headers=headers)
        if resp.status_code == 200:
            deleted_count += 1
    
    print(f"\n🧹 Cleanup: Deleted {deleted_count} test records")
    return deleted_count

def test_regression(token):
    """Test 7: Regression - meta/options, items 618, dashboard with empty data"""
    headers = get_headers(token)
    
    # Test meta/options
    resp = requests.get(f"{BASE_URL}/meta/options", headers=headers)
    meta_ok = resp.status_code == 200 and "shifts" in resp.json() and "proses_mesin" in resp.json()
    log_result("Regression: meta/options", meta_ok, 
               f"Status: {resp.status_code}, has shifts: {'shifts' in resp.json()}, has proses_mesin: {'proses_mesin' in resp.json()}")
    
    # Test items count
    resp = requests.get(f"{BASE_URL}/items", headers=headers)
    items_count = len(resp.json()) if resp.status_code == 200 else 0
    items_ok = items_count == 618
    log_result("Regression: items count = 618", items_ok, f"Count: {items_count}")
    
    # Test dashboard with empty data
    resp = requests.get(f"{BASE_URL}/dashboard/summary", headers=headers)
    dashboard_ok = resp.status_code == 200
    if dashboard_ok:
        data = resp.json()
        has_resume = "resume" in data
        has_trend = "smt_trend" in data
        log_result("Regression: dashboard returns 200 with empty data", 
                   has_resume and has_trend,
                   f"Status: {resp.status_code}, has resume: {has_resume}, has smt_trend: {has_trend}")
    else:
        log_result("Regression: dashboard returns 200 with empty data", False, 
                   f"Status: {resp.status_code}, Error: {resp.text[:200]}")
    
    return meta_ok and items_ok and dashboard_ok

def test_response_structure(token):
    """Test 1: Response structure"""
    headers = get_headers(token)
    resp = requests.get(f"{BASE_URL}/dashboard/summary", headers=headers)
    
    if resp.status_code != 200:
        log_result("Response Structure", False, f"Status: {resp.status_code}")
        return False
    
    data = resp.json()
    
    # Check resume object
    has_resume = "resume" in data
    if has_resume:
        resume = data["resume"]
        has_part_prod = "part_production" in resume
        has_lamp_assy = "lamp_assy" in resume
        has_shortage = "shortage" in resume
        has_achievement = "achievement" in resume
        
        # Check part_production fields
        if has_part_prod:
            pp = resume["part_production"]
            pp_ok = "total_plan" in pp and "act_prod" in pp and "pct" in pp
        else:
            pp_ok = False
        
        # Check lamp_assy fields
        if has_lamp_assy:
            la = resume["lamp_assy"]
            la_ok = "total_plan" in la and "act_prod" in la and "pct" in la
        else:
            la_ok = False
        
        # Check shortage fields
        if has_shortage:
            sh = resume["shortage"]
            sh_ok = ("total_part" in sh and "tidak_shortage" in sh and 
                     "potensi_shortage" in sh and "shortage" in sh)
        else:
            sh_ok = False
        
        # Check achievement fields
        if has_achievement:
            ach = resume["achievement"]
            ach_ok = "gt97" in ach and "mid" in ach and "lt90" in ach
            if ach_ok:
                for bucket in ["gt97", "mid", "lt90"]:
                    b = ach[bucket]
                    if not ("total_plan" in b and "act" in b and "average" in b):
                        ach_ok = False
                        break
        else:
            ach_ok = False
    else:
        pp_ok = la_ok = sh_ok = ach_ok = False
    
    # Check smt_trend
    has_trend = "smt_trend" in data
    if has_trend:
        trend = data["smt_trend"]
        if isinstance(trend, list) and len(trend) > 0:
            first_point = trend[0]
            trend_ok = "date" in first_point and "plan" in first_point and "actual" in first_point and "pct" in first_point
        else:
            trend_ok = True  # Empty trend is OK
    else:
        trend_ok = False
    
    all_ok = pp_ok and la_ok and sh_ok and ach_ok and trend_ok
    details = f"part_production: {pp_ok}, lamp_assy: {la_ok}, shortage: {sh_ok}, achievement: {ach_ok}, smt_trend: {trend_ok}"
    log_result("Response Structure", all_ok, details)
    
    return all_ok

def test_formulas(token):
    """Test 2: Formulas for part_production and lamp_assy"""
    headers = get_headers(token)
    
    # Use a specific test date
    test_date = "2026-01-15"
    
    # Get a real master item from the database
    resp = requests.get(f"{BASE_URL}/items?product=REGULER", headers=headers)
    if resp.status_code != 200 or len(resp.json()) == 0:
        log_result("Formulas Test", False, "Failed to get master items")
        return False
    
    master_item = resp.json()[0]
    ics_no = master_item["ics_no"]
    type_val = master_item["type"]
    lane = master_item["lane"]
    
    # Create test production records with known values
    # Record 1: SHIFT 3
    create_production_record(token, {
        "date": test_date,
        "lane": lane,
        "type": type_val,
        "ics_no": ics_no,
        "shift": "SHIFT 3",
        "plan_injection": 100,
        "act_injection": 90,
        "plan_eva": 50,
        "act_eva": 45,
        "plan_assy": 80,
        "act_assy": 75,
        "tt": 20
    })
    
    # Record 2: SHIFT 1 (same date, same item, different shift)
    create_production_record(token, {
        "date": test_date,
        "lane": lane,
        "type": type_val,
        "ics_no": ics_no,
        "shift": "SHIFT 1",
        "plan_injection": 120,
        "act_injection": 110,
        "plan_eva": 60,
        "act_eva": 55,
        "plan_assy": 90,
        "act_assy": 85,
        "tt": 20
    })
    
    # Expected calculations
    # part_production.total_plan = (100+50) + (120+60) = 330
    # part_production.act_prod = (90+45) + (110+55) = 300
    # part_production.pct = 300/330*100 = 90.9
    # lamp_assy.total_plan = 80 + 90 = 170
    # lamp_assy.act_prod = 75 + 85 = 160
    # lamp_assy.pct = 160/170*100 = 94.1
    
    expected_part_plan = 330.0
    expected_part_act = 300.0
    expected_part_pct = 90.9
    expected_assy_plan = 170.0
    expected_assy_act = 160.0
    expected_assy_pct = 94.1
    
    # Get dashboard summary with date filter
    resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}", headers=headers)
    
    if resp.status_code != 200:
        log_result("Formulas Test", False, f"Dashboard request failed: {resp.status_code}")
        return False
    
    data = resp.json()
    resume = data.get("resume", {})
    part_prod = resume.get("part_production", {})
    lamp_assy = resume.get("lamp_assy", {})
    
    # Verify part_production
    part_plan_ok = abs(part_prod.get("total_plan", 0) - expected_part_plan) < 0.1
    part_act_ok = abs(part_prod.get("act_prod", 0) - expected_part_act) < 0.1
    part_pct_ok = abs(part_prod.get("pct", 0) - expected_part_pct) < 0.1
    
    # Verify lamp_assy
    assy_plan_ok = abs(lamp_assy.get("total_plan", 0) - expected_assy_plan) < 0.1
    assy_act_ok = abs(lamp_assy.get("act_prod", 0) - expected_assy_act) < 0.1
    assy_pct_ok = abs(lamp_assy.get("pct", 0) - expected_assy_pct) < 0.1
    
    all_ok = part_plan_ok and part_act_ok and part_pct_ok and assy_plan_ok and assy_act_ok and assy_pct_ok
    
    details = (f"part_production: plan={part_prod.get('total_plan')} (exp {expected_part_plan}), "
               f"act={part_prod.get('act_prod')} (exp {expected_part_act}), "
               f"pct={part_prod.get('pct')} (exp {expected_part_pct}); "
               f"lamp_assy: plan={lamp_assy.get('total_plan')} (exp {expected_assy_plan}), "
               f"act={lamp_assy.get('act_prod')} (exp {expected_assy_act}), "
               f"pct={lamp_assy.get('pct')} (exp {expected_assy_pct})")
    
    log_result("Formulas Test", all_ok, details)
    return all_ok

def test_achievement_categories(token):
    """Test 3: Achievement categories per TYPE"""
    headers = get_headers(token)
    
    # Use a specific test date
    test_date = "2026-01-16"
    
    # Get 3 different master items with DIFFERENT types
    resp = requests.get(f"{BASE_URL}/items?product=REGULER", headers=headers)
    if resp.status_code != 200 or len(resp.json()) < 3:
        log_result("Achievement Categories Test", False, "Failed to get enough master items")
        return False
    
    all_items = resp.json()
    # Find 3 items with unique types
    items = []
    seen_types = set()
    for item in all_items:
        if item["type"] not in seen_types:
            items.append(item)
            seen_types.add(item["type"])
            if len(items) == 3:
                break
    
    if len(items) < 3:
        log_result("Achievement Categories Test", False, "Failed to find 3 items with unique types")
        return False
    
    # Type A: ~99% achievement (gt97)
    # plan_part = 1000, act_part = 990 → 99%
    create_production_record(token, {
        "date": test_date,
        "lane": items[0]["lane"],
        "type": items[0]["type"],
        "ics_no": items[0]["ics_no"],
        "shift": "SHIFT 3",
        "plan_injection": 1000,
        "act_injection": 990,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Type B: ~93% achievement (mid: 90-97)
    # plan_part = 1000, act_part = 930 → 93%
    create_production_record(token, {
        "date": test_date,
        "lane": items[1]["lane"],
        "type": items[1]["type"],
        "ics_no": items[1]["ics_no"],
        "shift": "SHIFT 3",
        "plan_injection": 1000,
        "act_injection": 930,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Type C: ~85% achievement (lt90)
    # plan_part = 1000, act_part = 850 → 85%
    create_production_record(token, {
        "date": test_date,
        "lane": items[2]["lane"],
        "type": items[2]["type"],
        "ics_no": items[2]["ics_no"],
        "shift": "SHIFT 3",
        "plan_injection": 1000,
        "act_injection": 850,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Get dashboard summary
    resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}", headers=headers)
    
    if resp.status_code != 200:
        log_result("Achievement Categories Test", False, f"Dashboard request failed: {resp.status_code}")
        return False
    
    data = resp.json()
    achievement = data.get("resume", {}).get("achievement", {})
    
    gt97 = achievement.get("gt97", {})
    mid = achievement.get("mid", {})
    lt90 = achievement.get("lt90", {})
    
    # Verify gt97: total_plan=1, act=1 (has act>0), average~99
    gt97_ok = (gt97.get("total_plan") == 1 and 
               gt97.get("act") == 1 and 
               98 <= gt97.get("average", 0) <= 100)
    
    # Verify mid: total_plan=1, act=1, average~93
    mid_ok = (mid.get("total_plan") == 1 and 
              mid.get("act") == 1 and 
              92 <= mid.get("average", 0) <= 94)
    
    # Verify lt90: total_plan=1, act=1, average~85
    lt90_ok = (lt90.get("total_plan") == 1 and 
               lt90.get("act") == 1 and 
               84 <= lt90.get("average", 0) <= 86)
    
    all_ok = gt97_ok and mid_ok and lt90_ok
    
    details = (f"gt97: total_plan={gt97.get('total_plan')} (exp 1), act={gt97.get('act')} (exp 1), avg={gt97.get('average')} (exp ~99); "
               f"mid: total_plan={mid.get('total_plan')} (exp 1), act={mid.get('act')} (exp 1), avg={mid.get('average')} (exp ~93); "
               f"lt90: total_plan={lt90.get('total_plan')} (exp 1), act={lt90.get('act')} (exp 1), avg={lt90.get('average')} (exp ~85)")
    
    log_result("Achievement Categories Test", all_ok, details)
    return all_ok

def test_shortage(token):
    """Test 4: Shortage per unique TYPE"""
    headers = get_headers(token)
    
    # Use a specific test date
    test_date = "2026-01-17"
    
    # Get 2 different master items
    resp = requests.get(f"{BASE_URL}/items?product=REGULER", headers=headers)
    if resp.status_code != 200 or len(resp.json()) < 2:
        log_result("Shortage Test", False, "Failed to get enough master items")
        return False
    
    items = resp.json()[:2]
    
    # Type 1: Create production with plan_assy=100, stock=50 → shortage (blc<0)
    create_production_record(token, {
        "date": test_date,
        "lane": items[0]["lane"],
        "type": items[0]["type"],
        "ics_no": items[0]["ics_no"],
        "shift": "SHIFT 3",
        "plan_injection": 0,
        "act_injection": 0,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 100,
        "act_assy": 0,
        "tt": 20
    })
    
    # Create stock record with total < plan_assy
    create_stock_record(token, {
        "date": test_date,
        "lane": items[0]["lane"],
        "type": items[0]["type"],
        "ics_no": items[0]["ics_no"],
        "shift": "SHIFT 3",
        "group1": 50,
        "group2": 0,
        "group3": 0,
        "group4": 0,
        "group5": 0,
        "group6": 0,
        "part_ragu": 0
    })
    
    # Type 2: Create production with plan_assy=50, stock=100 → tidak shortage (blc>=0)
    create_production_record(token, {
        "date": test_date,
        "lane": items[1]["lane"],
        "type": items[1]["type"],
        "ics_no": items[1]["ics_no"],
        "shift": "SHIFT 3",
        "plan_injection": 0,
        "act_injection": 0,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 50,
        "act_assy": 0,
        "tt": 20
    })
    
    # Create stock record with total >= plan_assy
    create_stock_record(token, {
        "date": test_date,
        "lane": items[1]["lane"],
        "type": items[1]["type"],
        "ics_no": items[1]["ics_no"],
        "shift": "SHIFT 3",
        "group1": 100,
        "group2": 0,
        "group3": 0,
        "group4": 0,
        "group5": 0,
        "group6": 0,
        "part_ragu": 0
    })
    
    # Get dashboard summary
    resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}", headers=headers)
    
    if resp.status_code != 200:
        log_result("Shortage Test", False, f"Dashboard request failed: {resp.status_code}")
        return False
    
    data = resp.json()
    shortage = data.get("resume", {}).get("shortage", {})
    
    # Verify: total_part=2, shortage=1, tidak_shortage=1 (or potensi_shortage=1)
    total_part = shortage.get("total_part", 0)
    shortage_count = shortage.get("shortage", 0)
    tidak_count = shortage.get("tidak_shortage", 0)
    potensi_count = shortage.get("potensi_shortage", 0)
    
    # We expect 2 types total, 1 shortage, and 1 either tidak or potensi
    total_ok = total_part == 2
    shortage_ok = shortage_count == 1
    other_ok = (tidak_count + potensi_count) == 1
    
    all_ok = total_ok and shortage_ok and other_ok
    
    details = (f"total_part={total_part} (exp 2), shortage={shortage_count} (exp 1), "
               f"tidak_shortage={tidak_count}, potensi_shortage={potensi_count} (exp sum=1)")
    
    log_result("Shortage Test", all_ok, details)
    return all_ok

def test_trend_aggregation(token):
    """Test 5: Trend per DATE aggregates across shifts WITHOUT double counting"""
    headers = get_headers(token)
    
    # Use a specific test date
    test_date = "2026-01-18"
    
    # Get a master item
    resp = requests.get(f"{BASE_URL}/items?product=REGULER", headers=headers)
    if resp.status_code != 200 or len(resp.json()) == 0:
        log_result("Trend Aggregation Test", False, "Failed to get master items")
        return False
    
    item = resp.json()[0]
    
    # Create TWO production records with SAME date+type, DIFFERENT shifts
    # Record 1: SHIFT 3
    create_production_record(token, {
        "date": test_date,
        "lane": item["lane"],
        "type": item["type"],
        "ics_no": item["ics_no"],
        "shift": "SHIFT 3",
        "plan_injection": 100,
        "act_injection": 90,
        "plan_eva": 50,
        "act_eva": 45,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Record 2: SHIFT 1 (same date, same type)
    create_production_record(token, {
        "date": test_date,
        "lane": item["lane"],
        "type": item["type"],
        "ics_no": item["ics_no"],
        "shift": "SHIFT 1",
        "plan_injection": 120,
        "act_injection": 110,
        "plan_eva": 60,
        "act_eva": 55,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Expected: trend point for this date should have:
    # plan = (100+50) + (120+60) = 330
    # actual = (90+45) + (110+55) = 300
    # pct = 300/330*100 = 90.9
    
    expected_plan = 330.0
    expected_actual = 300.0
    expected_pct = 90.9
    
    # Get dashboard summary
    resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}", headers=headers)
    
    if resp.status_code != 200:
        log_result("Trend Aggregation Test", False, f"Dashboard request failed: {resp.status_code}")
        return False
    
    data = resp.json()
    trend = data.get("smt_trend", [])
    
    # Find the trend point for our test date
    trend_point = None
    for point in trend:
        if point.get("date") == test_date:
            trend_point = point
            break
    
    if not trend_point:
        log_result("Trend Aggregation Test", False, f"Trend point for {test_date} not found")
        return False
    
    # Verify aggregation
    plan_ok = abs(trend_point.get("plan", 0) - expected_plan) < 0.1
    actual_ok = abs(trend_point.get("actual", 0) - expected_actual) < 0.1
    pct_ok = abs(trend_point.get("pct", 0) - expected_pct) < 0.1
    
    all_ok = plan_ok and actual_ok and pct_ok
    
    details = (f"date={test_date}: plan={trend_point.get('plan')} (exp {expected_plan}), "
               f"actual={trend_point.get('actual')} (exp {expected_actual}), "
               f"pct={trend_point.get('pct')} (exp {expected_pct})")
    
    log_result("Trend Aggregation Test", all_ok, details)
    return all_ok

def test_edge_cases(token):
    """Test 6: Edge cases - plan=0 no divide-by-zero, filters work"""
    headers = get_headers(token)
    
    # Use a specific test date
    test_date = "2026-01-19"
    
    # Get master items
    resp = requests.get(f"{BASE_URL}/items", headers=headers)
    if resp.status_code != 200 or len(resp.json()) < 2:
        log_result("Edge Cases Test", False, "Failed to get master items")
        return False
    
    items = resp.json()
    reguler_item = None
    spo_item = None
    
    for item in items:
        if item.get("product") == "REGULER" and not reguler_item:
            reguler_item = item
        elif item.get("product") == "SPO" and not spo_item:
            spo_item = item
        if reguler_item and spo_item:
            break
    
    if not reguler_item or not spo_item:
        log_result("Edge Cases Test", False, "Failed to find REGULER and SPO items")
        return False
    
    # Test 6a: Record with plan=0 should not cause divide-by-zero
    create_production_record(token, {
        "date": test_date,
        "lane": reguler_item["lane"],
        "type": reguler_item["type"],
        "ics_no": reguler_item["ics_no"],
        "shift": "SHIFT 3",
        "plan_injection": 0,
        "act_injection": 0,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Test 6b: Create a REGULER record for filter testing
    create_production_record(token, {
        "date": test_date,
        "lane": reguler_item["lane"],
        "type": reguler_item["type"],
        "ics_no": reguler_item["ics_no"],
        "shift": "SHIFT 1",
        "plan_injection": 100,
        "act_injection": 90,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Test 6c: Create a SPO record for filter testing
    create_production_record(token, {
        "date": test_date,
        "lane": spo_item["lane"],
        "type": spo_item["type"],
        "ics_no": spo_item["ics_no"],
        "shift": "SHIFT 1",
        "plan_injection": 200,
        "act_injection": 180,
        "plan_eva": 0,
        "act_eva": 0,
        "plan_assy": 0,
        "act_assy": 0,
        "tt": 20
    })
    
    # Test: Dashboard with plan=0 should not error
    resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}", headers=headers)
    no_error = resp.status_code == 200
    
    if not no_error:
        log_result("Edge Cases Test", False, f"Dashboard with plan=0 caused error: {resp.status_code}")
        return False
    
    data = resp.json()
    resume = data.get("resume", {})
    
    # pct should be 0 when plan=0, not error
    # With our data: plan_part = 0 + 100 + 200 = 300, act_part = 0 + 90 + 180 = 270
    # pct = 270/300*100 = 90.0
    pct = resume.get("part_production", {}).get("pct", None)
    pct_ok = pct is not None and pct >= 0
    
    # Test: Filter by product=REGULER
    resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={test_date}&date_to={test_date}&product=REGULER", headers=headers)
    filter_ok = resp.status_code == 200
    
    if filter_ok:
        data_filtered = resp.json()
        resume_filtered = data_filtered.get("resume", {})
        # With REGULER filter: plan_part = 0 + 100 = 100, act_part = 0 + 90 = 90
        # pct = 90/100*100 = 90.0
        plan_filtered = resume_filtered.get("part_production", {}).get("total_plan", 0)
        act_filtered = resume_filtered.get("part_production", {}).get("act_prod", 0)
        # Should be less than unfiltered (which includes SPO)
        filter_works = plan_filtered < 300 and act_filtered < 270
    else:
        filter_works = False
    
    # Test: Date filter
    tomorrow = "2026-01-20"
    resp = requests.get(f"{BASE_URL}/dashboard/summary?date_from={tomorrow}&date_to={tomorrow}", headers=headers)
    date_filter_ok = resp.status_code == 200
    if date_filter_ok:
        data_tomorrow = resp.json()
        resume_tomorrow = data_tomorrow.get("resume", {})
        # Should have no data for tomorrow
        plan_tomorrow = resume_tomorrow.get("part_production", {}).get("total_plan", 0)
        date_filter_works = plan_tomorrow == 0
    else:
        date_filter_works = False
    
    all_ok = no_error and pct_ok and filter_works and date_filter_works
    
    details = (f"plan=0 no error: {no_error}, pct valid: {pct_ok} (pct={pct}), "
               f"product filter works: {filter_works}, date filter works: {date_filter_works}")
    
    log_result("Edge Cases Test", all_ok, details)
    return all_ok

def main():
    """Main test execution"""
    print("=" * 80)
    print("DASHBOARD SUMMARY ENDPOINT COMPREHENSIVE TEST")
    print("=" * 80)
    print()
    
    try:
        # Login
        print("🔐 Logging in...")
        token = login()
        print("✅ Login successful\n")
        
        # Test 7: Regression (run first with empty data)
        print("📋 Test 7: Regression Tests")
        print("-" * 80)
        test_regression(token)
        print()
        
        # Test 1: Response structure
        print("📋 Test 1: Response Structure")
        print("-" * 80)
        test_response_structure(token)
        print()
        
        # Test 2: Formulas
        print("📋 Test 2: Formulas (part_production & lamp_assy)")
        print("-" * 80)
        test_formulas(token)
        print()
        
        # Test 3: Achievement categories
        print("📋 Test 3: Achievement Categories per TYPE")
        print("-" * 80)
        test_achievement_categories(token)
        print()
        
        # Test 4: Shortage
        print("📋 Test 4: Shortage per Unique TYPE")
        print("-" * 80)
        test_shortage(token)
        print()
        
        # Test 5: Trend aggregation
        print("📋 Test 5: Trend Aggregation (cross-shift)")
        print("-" * 80)
        test_trend_aggregation(token)
        print()
        
        # Test 6: Edge cases
        print("📋 Test 6: Edge Cases (plan=0, filters)")
        print("-" * 80)
        test_edge_cases(token)
        print()
        
        # Cleanup
        print("=" * 80)
        cleanup_test_data(token)
        print()
        
        # Verify items count after cleanup
        print("🔍 Verifying items count after cleanup...")
        headers = get_headers(token)
        resp = requests.get(f"{BASE_URL}/items", headers=headers)
        final_count = len(resp.json()) if resp.status_code == 200 else 0
        if final_count == 618:
            print(f"✅ Items count verified: {final_count} (correct)")
        else:
            print(f"❌ Items count mismatch: {final_count} (expected 618)")
        print()
        
        # Summary
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        passed = sum(1 for r in test_results if r["passed"])
        total = len(test_results)
        print(f"Total: {passed}/{total} tests passed")
        print()
        
        for result in test_results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status}: {result['test']}")
        
        print()
        print("=" * 80)
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {total - passed} TEST(S) FAILED")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
