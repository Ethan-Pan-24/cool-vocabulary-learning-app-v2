import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gemma3:4b"

# Candidates for OpenWebUI OpenAI-compatible endpoint
candidates = [
    "https://chat.otlab.org/api",
    "https://chat.otlab.org/api/v1",
    "https://chat.otlab.org/v1"
]

payload = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Return a JSON object with 'status': 'ok'"}],
    "temperature": 0.1,
    "response_format": {"type": "json_object"}
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

for url in candidates:
    print(f"\n--- Testing URL: {url}/chat/completions ---")
    try:
        response = requests.post(f"{url}/chat/completions", json=payload, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response Header Content-Type: {response.headers.get('Content-Type')}")
        try:
            print(f"JSON Output: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        except:
            print(f"Raw Content (First 200 chars): {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
