import requests
import json

def test_url(url):
    print(f"\nTesting URL: {url}")
    try:
        r = requests.get(url, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                print("Response: JSON (Success)")
                if "error" in data:
                    print(f"ERROR content: {data['error']}")
                    if "traceback" in data:
                        print(f"TRACEBACK:\n{data['traceback']}")
            except:
                print(f"Response: {r.text[:100]}...")
        else:
            print(f"Error Response: {r.text[:200]}")
    except Exception as e:
        print(f"Exception: {str(e)}")

print("=" * 60)
print("SERVER HEALTH CHECK")
print("=" * 60)

# Test root or some simple endpoint
test_url("http://localhost:8000/admin_api/stats?course_id=1")
test_url("http://localhost:8000/admin_api/efficiency_plot?course_id=1")

print("\n" + "=" * 60)
