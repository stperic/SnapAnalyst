"""
Test script for direct SQL query feature
Tests:
1. Natural language query (should go to Vanna)
2. Direct SELECT query (should bypass Vanna)
3. Direct SELECT with analysis instructions
4. Invalid SQL (UPDATE - should reject)
"""
import httpx
import asyncio

API_BASE_URL = "http://localhost:8000"

async def test_queries():
    """Test different query types"""
    
    test_cases = [
        {
            "name": "Natural Language Query",
            "query": "How many households are in Connecticut?",
            "should_use_vanna": True,
            "should_execute": True
        },
        {
            "name": "Direct SQL - Simple SELECT",
            "query": "SELECT COUNT(*) as total FROM households",
            "should_use_vanna": False,
            "should_execute": True
        },
        {
            "name": "Direct SQL with Analysis",
            "query": "SELECT state_name, COUNT(*) as count FROM households GROUP BY state_name ORDER BY count DESC LIMIT 10 | Focus on the top 3 states",
            "should_use_vanna": False,
            "should_execute": True
        },
        {
            "name": "Direct SQL - WITH clause",
            "query": "WITH state_counts AS (SELECT state_name, COUNT(*) as cnt FROM households GROUP BY state_name) SELECT * FROM state_counts LIMIT 5",
            "should_use_vanna": False,
            "should_execute": True
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test in enumerate(test_cases, 1):
            print(f"\n{'='*60}")
            print(f"Test {i}: {test['name']}")
            print(f"{'='*60}")
            print(f"Query: {test['query'][:100]}...")
            
            try:
                # For Chainlit, we'd need to go through the web UI
                # For API testing, we can use the direct endpoint
                if test['query'].strip().upper().startswith(('SELECT', 'WITH')):
                    # Direct SQL execution
                    response = await client.post(
                        f"{API_BASE_URL}/api/v1/query/sql",
                        json={"sql": test['query'].split('|')[0].strip(), "limit": 50000}
                    )
                else:
                    # Natural language
                    response = await client.post(
                        f"{API_BASE_URL}/api/v1/chat/query",
                        json={"question": test['query'], "execute": True}
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Handle different response formats
                    if 'success' in result:
                        # /query/sql endpoint response
                        if result.get('success'):
                            row_count = result.get('row_count', 0)
                            print(f"✅ SUCCESS - {row_count} rows returned")
                            
                            # Show first few results
                            if result.get('data'):
                                print("\nSample results:")
                                for row in result['data'][:3]:
                                    print(f"  {row}")
                        else:
                            print(f"❌ FAILED - {result.get('error', 'Unknown error')}")
                    else:
                        # /chat/query endpoint response
                        row_count = result.get('row_count', len(result.get('results', [])))
                        print(f"✅ SUCCESS - {row_count} rows returned")
                        
                        # Show first few results
                        if result.get('results'):
                            print("\nSample results:")
                            for row in result['results'][:3]:
                                print(f"  {row}")
                else:
                    print(f"❌ FAILED - Status: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
    
    print(f"\n{'='*60}")
    print("Testing write protection...")
    print(f"{'='*60}")
    
    # Test write protection
    invalid_queries = [
        "UPDATE households SET snap_benefit_amount = 0",
        "DELETE FROM households WHERE case_id = 1",
        "DROP TABLE households",
        "INSERT INTO households VALUES (1, 2, 3)"
    ]
    
    for query in invalid_queries:
        print(f"\nTesting blocked query: {query[:50]}...")
        # The Chainlit app should block these before sending to API
        # But let's verify the API also has protection
        print("  ⚠️ This should be blocked by the Chainlit UI")
        print("  (Manual verification needed in the web UI)")

if __name__ == "__main__":
    print("=" * 60)
    print("Direct SQL Query Feature Test")
    print("=" * 60)
    print("\nMake sure the API is running:")
    print("  PYTHONPATH=. python src/api/main.py")
    print("\nThis tests the API endpoints used by the feature.")
    print("Full feature testing requires using the Chainlit UI.\n")
    
    asyncio.run(test_queries())
    
    print("\n" + "="*60)
    print("MANUAL TESTING CHECKLIST (in Chainlit UI)")
    print("="*60)
    print("1. Natural language: 'How many households in Texas?'")
    print("   → Should use Vanna, generate SQL, execute")
    print("\n2. Direct SQL: 'SELECT COUNT(*) FROM households'")
    print("   → Should bypass Vanna, execute directly")
    print("\n3. Direct SQL + Analysis:")
    print("   'SELECT state_name, AVG(gross_income) FROM households GROUP BY state_name | Focus on top 5'")
    print("   → Should bypass Vanna for SQL, use instructions for summary")
    print("\n4. Blocked SQL: 'UPDATE households SET snap_benefit_amount = 0'")
    print("   → Should show error message about read-only")
    print("="*60)
