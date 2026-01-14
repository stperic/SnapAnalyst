#!/bin/bash
# Master Filter Test Script

echo "🧪 SnapAnalyst Master Filter - Quick Test"
echo "=========================================="
echo

# Test 1: Get options
echo "✅ Test 1: Get available filter options"
curl -s http://localhost:8000/api/v1/filter/options | jq -r '"States: \(.states | length), Years: \(.fiscal_years | join(", "))"'
echo

# Test 2: Set state filter
echo "✅ Test 2: Set filter to Connecticut"
curl -s -X POST http://localhost:8000/api/v1/filter/set \
     -H "Content-Type: application/json" \
     -d '{"state": "Connecticut"}' | jq -r '.message'
echo

# Test 3: Check status
echo "✅ Test 3: Check filter status"
curl -s http://localhost:8000/api/v1/filter/ | jq -r '.description'
echo

# Test 4: Test SQL injection
echo "✅ Test 4: Test SQL injection"
curl -s "http://localhost:8000/api/v1/filter/test-sql?sql=SELECT%20*%20FROM%20households%20LIMIT%2010" | jq '.filter_applied'
echo

# Test 5: Clear filter
echo "✅ Test 5: Clear filter"
curl -s -X POST http://localhost:8000/api/v1/filter/clear | jq -r '.message'
echo

# Test 6: Verify cleared
echo "✅ Test 6: Verify filter cleared"
curl -s http://localhost:8000/api/v1/filter/ | jq -r '.description'
echo

echo "=========================================="
echo "🎉 All tests complete!"
echo
echo "Next steps:"
echo "1. Open http://localhost:8001"
echo "2. Click Settings (⚙️)"
echo "3. Select a State and/or Year"
echo "4. Ask any question - it will be filtered!"
echo "5. Type /download - export will be filtered!"
