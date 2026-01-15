#!/usr/bin/env python3
"""
Test script to verify enhanced Vanna training with code lookups
"""
import asyncio
import httpx

async def test_queries():
    """Test various queries using code lookups"""
    
    base_url = "http://localhost:8000"
    
    test_queries = [
        "Show me all overissuance cases",
        "What are the most common error types?",
        "Find all wage errors",
        "Show households with elderly members in California",
        "What's the average income by state?",
        "Find households entitled to expedited service but didn't receive it on time",
        "Show categorically eligible households"
    ]
    
    print("=" * 80)
    print("Testing Enhanced Vanna Training with Code Lookups")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, query in enumerate(test_queries, 1):
            print(f"\n{i}. Query: {query}")
            print("-" * 80)
            
            try:
                response = await client.post(
                    f"{base_url}/api/v1/chat/query",
                    json={"query": query}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    sql = data.get("sql", "No SQL generated")
                    print(f"Generated SQL:\n{sql}")
                    
                    # Show if query returned results
                    results = data.get("results", [])
                    if results:
                        print(f"✅ Query successful - {len(results)} rows returned")
                    else:
                        print("⚠️  Query returned no results")
                else:
                    print(f"❌ Error: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Exception: {e}")
            
            # Small delay between queries
            await asyncio.sleep(1)
    
    print("\n" + "=" * 80)
    print("Testing Complete!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_queries())
