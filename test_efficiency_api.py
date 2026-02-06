import requests
import json

# Test the efficiency analysis endpoint
url = "http://localhost:8000/admin_api/efficiency_plot?course_id=1"

print("Testing efficiency analysis endpoint...")
print(f"URL: {url}")
print("=" * 60)

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print("\nResponse Body:")
    
    if response.status_code == 200:
        data = response.json()
        if "error" in data:
            print(f"ERROR: {data['error']}")
        else:
            print("SUCCESS!")
            print(f"- Has image: {'image' in data}")
            print(f"- Has statistics: {'statistics' in data}")
            if 'statistics' in data:
                stats = data['statistics']
                print(f"\nStatistics keys: {stats.keys()}")
                if 'descriptive' in stats:
                    desc = stats['descriptive']
                    print(f"Total students: {desc.get('total_students')}")
                    print(f"Num groups: {desc.get('num_groups')}")
    else:
        print(f"Error response:")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
            
except Exception as e:
    print(f"Exception occurred: {type(e).__name__}")
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
