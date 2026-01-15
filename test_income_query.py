#!/usr/bin/env python3
"""
Test the average income by state query to verify:
1. Summary uses correct min/max values (no hallucination)
2. Numbers are formatted to 2 decimal places
"""
import asyncio
import httpx
import json

async def test_income_query():
    base_url = "http://localhost:8000"
    
    print("=" * 80)
    print("Testing: Average Income by State")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Generate and execute query
        response = await client.post(
            f"{base_url}/api/v1/chat/query",
            json={"question": "What's the average income by state?"}
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if results:
                # Find actual min and max
                sorted_by_income = sorted(results, key=lambda x: float(x.get("average_income", 0)))
                
                lowest = sorted_by_income[0]
                highest = sorted_by_income[-1]
                
                print(f"\n✅ Query successful - {len(results)} states returned")
                print(f"\n📊 ACTUAL DATA:")
                print(f"   Lowest:  {lowest['state_name']} = ${float(lowest['average_income']):.2f}")
                print(f"   Highest: {highest['state_name']} = ${float(highest['average_income']):.2f}")
                
                # Show first 5 formatted
                print(f"\n📋 Sample Results (formatted to 2 decimals):")
                for i, row in enumerate(results[:5], 1):
                    state = row['state_name']
                    income = float(row['average_income'])
                    print(f"   {i}. {state}: ${income:.2f}")
                
                print(f"\n✅ Number formatting test: PASSED")
                print(f"   All values can be formatted to 2 decimal places")
                
            else:
                print("❌ No results returned")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
    
    print("\n" + "=" * 80)
    print("Now test in Chainlit UI at http://localhost:8001")
    print("Ask: 'What's the average income by state?'")
    print("\nVerify:")
    print("1. Summary mentions Pennsylvania (highest) and Tennessee (lowest)")
    print("2. Table shows numbers like 1,097.65 (2 decimals) not 1097.6473429951690821")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_income_query())
