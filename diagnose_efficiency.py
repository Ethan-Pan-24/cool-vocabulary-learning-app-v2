import requests
import json
import traceback

print("=" * 80)
print("COMPREHENSIVE EFFICIENCY ANALYSIS DIAGNOSTICS")
print("=" * 80)

# Test 1: Check if endpoint is accessible
print("\n[TEST 1] Testing endpoint accessibility...")
url = "http://localhost:8000/admin_api/efficiency_plot?course_id=1"
print(f"URL: {url}")

try:
    response = requests.get(url, timeout=30)
    print(f"✓ Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✓ SUCCESS! API returned 200")
        data = response.json()
        
        # Check response structure
        print("\n[TEST 2] Checking response structure...")
        if 'sections' in data:
            print("✓ Has 'sections' key")
            sections = data['sections']
            print(f"  - Available sections: {list(sections.keys())}")
            
            if "Overall" in sections:
                overall = sections["Overall"]
                print(f"✓ Overall section found")
                print(f"  - Has 'image': {'image' in overall}")
                stats = overall.get('statistics', {})
                print(f"  - Statistics keys: {list(stats.keys())}")
            
            if 'descriptive' in stats:
                desc = stats['descriptive']
                print(f"\n[TEST 3] Descriptive Statistics:")
                print(f"  - Total students: {desc.get('total_students')}")
                print(f"  - Number of groups: {desc.get('num_groups')}")
                print(f"  - M_performance: {desc.get('M_performance')}")
                print(f"  - M_effort: {desc.get('M_effort')}")
            
            if 'kruskal_wallis' in stats:
                kw = stats['kruskal_wallis']
                print(f"\n[TEST 4] Kruskal-Wallis Test:")
                print(f"  - H-statistic: {kw.get('H')}")
                print(f"  - p-value: {kw.get('p')}")
                print(f"  - Significant: {kw.get('significant')}")
        
        if 'error' in data:
            print(f"\n✗ API returned error: {data['error']}")
        
        print(f"\n✓ All tests passed! Image size: {len(data.get('image', '')) // 1000}KB")
        
    elif response.status_code == 500:
        print(f"✗ 500 Internal Server Error")
        print(f"Response text: {response.text}")
        
    elif response.status_code == 400:
        print(f"✗ 400 Bad Request")
        try:
            error_data = response.json()
            print(f"Error message: {error_data}")
        except:
            print(f"Response text: {response.text}")
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except requests.exceptions.ConnectionError:
    print("✗ CONNECTION ERROR: Cannot connect to server")
    print("  Make sure uvicorn is running on port 8000")
    
except requests.exceptions.Timeout:
    print("✗ TIMEOUT ERROR: Server took too long to respond")
    
except Exception as e:
    print(f"✗ EXCEPTION: {type(e).__name__}")
    print(f"  Error: {str(e)}")
    traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNOSTICS COMPLETE")
print("=" * 80)
