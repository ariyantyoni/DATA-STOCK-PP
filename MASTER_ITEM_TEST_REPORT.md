# Master Item Schema Change - Test Report

## Test Date: 2026
## Tester: Testing Agent
## Application: PART PRODUCTION (part_production database)

---

## EXECUTIVE SUMMARY

**Overall Status: PARTIAL PASS** ⚠️

The Master Item schema change has been implemented correctly for NEW data operations (create, update, import), but a legacy data issue exists where the 119 pre-existing seeded items still contain the old `led_rank` field in the database.

---

## SCHEMA CHANGE DETAILS

**Change Made:**
- **REMOVED:** `led_rank` field (label: "LED Rank")
- **ADDED:** `proses_mesin` field (label: "PROSES MESIN", type: text)

**Location:** `backend/server.py` - `FIELDS["items"]` (line 262-264)

**Current Schema:**
```python
"items": [
    ("lane", "Lane", False),
    ("product", "Product", False),
    ("type", "Type", False),
    ("ics_no", "ICS No.", False),
    ("tt", "T/T (detik)", True),
    ("tt_assy", "T/T Assy (detik/unit)", True),
    ("material_per_unit", "Kebutuhan Material per Unit Assy", True),
    ("proses_mesin", "PROSES MESIN", False)
]
```

---

## TEST RESULTS

### ✅ TEST 1: CREATE Master Item with proses_mesin
**Status: PASS**

- Created item with: `{"lane":"LT1", "product":"REGULER", "type":"QATEST", "ics_no":"12345", "tt":12, "tt_assy":5, "material_per_unit":1, "proses_mesin":"CNC-01"}`
- ✓ Response contains `proses_mesin="CNC-01"`
- ✓ Response does NOT contain `led_rank`
- ✓ `cap_h` computed correctly: 300.0 (expected: 3600/12 = 300.0)
- ✓ Item created with ID: `6abc95f7e1dd70a74e8743d6`

### ✅ TEST 2: GET Items List
**Status: PASS**

- Retrieved 120 items (119 base + 1 test item)
- ✓ Test item found in list
- ✓ Test item has `proses_mesin="CNC-01"`
- ✓ Test item does NOT have `led_rank`

### ✅ TEST 3: UPDATE Item proses_mesin
**Status: PASS**

- Updated `proses_mesin` from "CNC-01" to "CNC-02"
- ✓ Update successful
- ✓ Change persisted in database

### ✅ TEST 4: Import Template Column Headers
**Status: PASS**

- Downloaded template from `/api/import/items/template`
- ✓ Template downloaded successfully
- ✓ Column headers: `['Lane', 'Product', 'Type', 'ICS No.', 'T/T (detik)', 'T/T Assy (detik/unit)', 'Kebutuhan Material per Unit Assy', 'PROSES MESIN']`
- ✓ "PROSES MESIN" column present
- ✓ "LED Rank" column correctly absent
- ✓ All expected columns present

### ✅ TEST 5: Import Functionality
**Status: PASS**

- Created Excel file with new schema including `proses_mesin` field
- Imported item: `{"lane":"LT2", "product":"REGULER", "type":"IMPORT-TEST", "ics_no":"99999", "tt":15, "tt_assy":6, "material_per_unit":1, "proses_mesin":"LASER-01"}`
- ✓ Import preview successful
- ✓ `proses_mesin="LASER-01"` present in preview
- ✓ `led_rank` correctly absent in preview
- ✓ Import confirm successful (1 inserted)
- ✓ Imported item retrieved with ICS No: "0000099999" (padded)
- ✓ Imported item has `proses_mesin="LASER-01"`
- ✓ Imported item does NOT have `led_rank` field

### ✅ TEST 6: DELETE Test Items
**Status: PASS**

- ✓ Test items deleted successfully
- ✓ Final item count: 119 (correct)

### ❌ TEST 7: Verify Base Items (Legacy Data Issue)
**Status: FAIL**

- ✓ Item count correct: 119 items
- ❌ **All 119 pre-existing items STILL CONTAIN `led_rank` field**
- ℹ️ 0 items have `proses_mesin` populated (acceptable for old items)

**Example of legacy item:**
```json
{
  "lane": "K-13",
  "product": "",
  "type": "SUB ASSY HL 20MY",
  "ics_no": "5893717600",
  "tt": 61.63,
  "tt_assy": 0.0,
  "material_per_unit": 1.0,
  "led_rank": "",
  "cap_h": 58.41,
  "created_at": "2026-09-28T08:04:36.804178+00:00",
  "id": "6aba1f94fb773b0c8570a78d"
}
```

---

## ROOT CAUSE ANALYSIS

### Why Legacy Items Still Have led_rank

1. **Schema Definition:** The `FIELDS["items"]` schema was updated to remove `led_rank` and add `proses_mesin`

2. **normalize() Function:** This function (line 328-341) filters and validates fields based on the current schema, but it's ONLY used when WRITING data:
   - POST `/api/items` (create)
   - PUT `/api/items/{id}` (update)
   - POST `/api/import/items/confirm` (import)

3. **GET Endpoint:** The list_items function (line 544-564) uses:
   ```python
   docs = await coll.find(build_query(p)).sort(cfg["sort"]).to_list(5000)
   out = [clean(d) for d in docs]
   ```
   
4. **clean() Function:** This function (line 159-162) only converts `_id` to `id`, it does NOT filter fields based on the current schema:
   ```python
   def clean(doc: dict) -> dict:
       doc = dict(doc)
       doc["id"] = str(doc.pop("_id"))
       return doc
   ```

5. **Result:** The API returns ALL fields from the database, including obsolete fields like `led_rank` that are no longer in the schema

---

## IMPACT ASSESSMENT

### What Works Correctly ✅
- Creating new items (proses_mesin present, led_rank absent)
- Updating items (proses_mesin can be modified)
- Importing items (uses new schema)
- Import/Export templates (show correct column headers)
- cap_h computation (working correctly)

### What Has Issues ❌
- GET `/api/items` returns `led_rank` for 119 pre-existing items
- Schema inconsistency between old and new items
- API responses don't match the defined schema for legacy data

### Functional Impact
- **No errors or crashes** - items list without error as required
- **No data corruption** - all data intact
- **Schema inconsistency** - old items have different fields than new items
- **Frontend impact** - If frontend expects consistent schema, may need handling for optional fields

---

## RECOMMENDATIONS

### Option 1: Data Migration (Recommended)
Run a MongoDB update to remove the `led_rank` field from all existing items:

```javascript
db.items.update_many({}, {$unset: {led_rank: ""}})
```

**Pros:**
- Clean database schema
- Consistent API responses
- One-time operation

**Cons:**
- Requires database access
- Irreversible (unless backup exists)

### Option 2: API Response Filtering
Modify the `clean()` function or the list_items endpoint to filter fields based on `FIELDS[module]`:

```python
def clean_with_schema(doc: dict, module: str) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    
    # Filter to only include fields in current schema
    allowed_fields = {key for key, _, _ in FIELDS[module]}
    allowed_fields.add("id")
    allowed_fields.add("created_at")
    allowed_fields.add("updated_at")
    allowed_fields.add("created_by")
    allowed_fields.add("created_by_name")
    allowed_fields.add("updated_by")
    allowed_fields.add("updated_by_name")
    
    # Add computed fields
    if module == "items":
        allowed_fields.add("cap_h")
    
    return {k: v for k, v in doc.items() if k in allowed_fields}
```

**Pros:**
- No database changes needed
- Reversible
- Consistent API responses

**Cons:**
- Code changes required
- May hide data that exists in database
- Need to maintain allowed fields list

### Option 3: Do Nothing
Accept that legacy items have different fields than new items.

**Pros:**
- No changes needed
- Data preserved

**Cons:**
- Schema inconsistency
- May confuse frontend developers
- Not following best practices

---

## CONCLUSION

The Master Item schema change has been **implemented correctly** for all NEW data operations. The issue is with LEGACY data that was seeded before the schema change.

**Recommendation:** Implement **Option 1 (Data Migration)** to remove `led_rank` from all 119 existing items. This is the cleanest solution and ensures schema consistency across all items.

**Alternative:** If data migration is not possible, implement **Option 2 (API Response Filtering)** to ensure API responses match the current schema definition.

---

## TEST ARTIFACTS

- `/app/backend_test_master_item.py` - Main test suite (7 tests)
- `/app/backend_test_import.py` - Import functionality test
- `/app/check_fields.py` - Field verification script
- `/app/check_import.py` - Import verification script

---

## REQUIREMENT COMPLIANCE

**Original Requirements:**
1. ✅ CREATE a master item with proses_mesin - **PASS**
2. ✅ Verify response contains proses_mesin and NOT led_rank - **PASS** (for new items)
3. ✅ Verify cap_h is computed - **PASS**
4. ✅ GET /api/items list and confirm created item - **PASS**
5. ✅ UPDATE item changing proses_mesin - **PASS**
6. ✅ Import/Export template shows "PROSES MESIN" and NO "LED Rank" - **PASS**
7. ✅ DELETE test items - **PASS**
8. ⚠️ Confirm 119 pre-existing items still list without error - **PARTIAL PASS** (list without error, but contain led_rank)

**Overall Compliance: 7.5/8 (93.75%)**

---

**Report Generated:** 2026
**Testing Agent:** E2 (Testing Sub-Agent)
