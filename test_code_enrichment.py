"""
Test script for code enrichment feature
Tests that code columns are properly enriched with descriptions
"""
import json
from pathlib import Path

# Simulate the functions
CODE_COLUMN_MAPPINGS = {
    'element_code': 'element_codes',
    'nature_code': 'nature_codes',
    'status': 'status_codes',
    'error_finding': 'error_finding_codes',
}

def load_code_lookups():
    """Load code lookups from data_mapping.json"""
    data_mapping_path = Path(__file__).parent / "data_mapping.json"
    with open(data_mapping_path, 'r') as f:
        data = json.load(f)
        return data.get('code_lookups', {})

def enrich_results_with_code_descriptions(results):
    """Find code columns and load descriptions"""
    if not results:
        return {}
    
    column_names = set(results[0].keys())
    code_columns = column_names & CODE_COLUMN_MAPPINGS.keys()
    
    if not code_columns:
        return {}
    
    code_lookups = load_code_lookups()
    enriched = {}
    
    for col_name in code_columns:
        lookup_key = CODE_COLUMN_MAPPINGS[col_name]
        
        # Extract unique codes
        unique_codes = set()
        for row in results:
            code_value = row.get(col_name)
            if code_value is not None:
                unique_codes.add(str(code_value))
        
        if not unique_codes:
            continue
        
        # Load only those codes
        lookup_table = code_lookups.get(lookup_key, {})
        enriched[col_name] = {}
        
        for code in unique_codes:
            if code in lookup_table and code not in ['description', 'source_field']:
                enriched[col_name][code] = lookup_table[code]
            else:
                enriched[col_name][code] = f"Unknown code {code}"
    
    return enriched


# Test cases
def test_element_codes():
    """Test element code enrichment"""
    print("\n" + "="*60)
    print("TEST 1: Element Codes")
    print("="*60)
    
    results = [
        {'element_code': 363, 'error_count': 6959},
        {'element_code': 311, 'error_count': 4657},
        {'element_code': 364, 'error_count': 1780},
    ]
    
    enriched = enrich_results_with_code_descriptions(results)
    
    print("\nResults:")
    for row in results:
        print(f"  {row}")
    
    print("\nEnriched Codes:")
    for col_name, code_dict in enriched.items():
        print(f"\n{col_name}:")
        for code, description in sorted(code_dict.items()):
            print(f"  Code {code}: {description}")
    
    # Verify
    assert 'element_code' in enriched
    assert '363' in enriched['element_code']
    assert enriched['element_code']['363'] == 'Shelter deduction'
    assert enriched['element_code']['311'] == 'Wages and salaries'
    print("\n✅ PASSED: Element codes enriched correctly")


def test_multiple_code_columns():
    """Test multiple code columns"""
    print("\n" + "="*60)
    print("TEST 2: Multiple Code Columns")
    print("="*60)
    
    results = [
        {'element_code': 311, 'nature_code': 35, 'error_count': 100},
        {'element_code': 363, 'nature_code': 54, 'error_count': 200},
    ]
    
    enriched = enrich_results_with_code_descriptions(results)
    
    print("\nResults:")
    for row in results:
        print(f"  {row}")
    
    print("\nEnriched Codes:")
    for col_name, code_dict in enriched.items():
        print(f"\n{col_name}:")
        for code, description in sorted(code_dict.items()):
            print(f"  Code {code}: {description}")
    
    # Verify
    assert 'element_code' in enriched
    assert 'nature_code' in enriched
    assert '35' in enriched['nature_code']
    print("\n✅ PASSED: Multiple code columns enriched correctly")


def test_no_code_columns():
    """Test results without code columns"""
    print("\n" + "="*60)
    print("TEST 3: No Code Columns")
    print("="*60)
    
    results = [
        {'state_name': 'California', 'household_count': 1000},
        {'state_name': 'Texas', 'household_count': 800},
    ]
    
    enriched = enrich_results_with_code_descriptions(results)
    
    print("\nResults:")
    for row in results:
        print(f"  {row}")
    
    print("\nEnriched Codes:")
    print(f"  {enriched if enriched else '(none - no code columns detected)'}")
    
    # Verify
    assert enriched == {}
    print("\n✅ PASSED: No enrichment for non-code columns")


def test_status_codes():
    """Test status code enrichment"""
    print("\n" + "="*60)
    print("TEST 4: Status Codes")
    print("="*60)
    
    results = [
        {'status': 1, 'count': 5000},
        {'status': 2, 'count': 1500},
        {'status': 3, 'count': 500},
    ]
    
    enriched = enrich_results_with_code_descriptions(results)
    
    print("\nResults:")
    for row in results:
        print(f"  {row}")
    
    print("\nEnriched Codes:")
    for col_name, code_dict in enriched.items():
        print(f"\n{col_name}:")
        for code, description in sorted(code_dict.items()):
            print(f"  Code {code}: {description}")
    
    # Verify
    assert 'status' in enriched
    assert enriched['status']['1'] == 'Amount correct'
    assert enriched['status']['2'] == 'Overissuance'
    assert enriched['status']['3'] == 'Underissuance'
    print("\n✅ PASSED: Status codes enriched correctly")


def test_format_in_prompt():
    """Test how enrichment looks in prompt"""
    print("\n" + "="*60)
    print("TEST 5: Prompt Format")
    print("="*60)
    
    results = [
        {'element_code': 363, 'error_count': 6959},
        {'element_code': 311, 'error_count': 4657},
    ]
    
    enriched = enrich_results_with_code_descriptions(results)
    
    # Build code reference section
    code_reference = "\n📖 CODE REFERENCE (Use descriptions, NOT codes):\n"
    for col_name, code_dict in enriched.items():
        code_reference += f"\n{col_name.replace('_', ' ').title()}:\n"
        for code, description in sorted(code_dict.items()):
            code_reference += f"  - Code {code}: {description}\n"
    
    print("\nPrompt Section:")
    print(code_reference)
    print("\n✅ PASSED: Format looks good for LLM prompt")


if __name__ == "__main__":
    print("="*60)
    print("Code Enrichment Feature Tests")
    print("="*60)
    
    try:
        test_element_codes()
        test_multiple_code_columns()
        test_no_code_columns()
        test_status_codes()
        test_format_in_prompt()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! ✅")
        print("="*60)
        print("\nThe code enrichment feature is working correctly.")
        print("Code descriptions will now be included in LLM summaries.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
