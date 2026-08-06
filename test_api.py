import requests
import json

print("="*50)
print("🚀 LUMINA API TEST")
print("="*50)

# Test 1: Root
print("\n1. Testing Root Endpoint...")
try:
    r = requests.get("http://localhost:8000/")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Project: {data.get('project')}")
        print(f"   Status: {data.get('status')}")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("   Make sure server is running: python run.py")
    exit()

# Test 2: Health
print("\n2. Testing Health Endpoint...")
try:
    r = requests.get("http://localhost:8000/health")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Response: {r.json()}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Score - Scam Call
print("\n3. Testing Score Endpoint (Scam Call)...")
payload = {
    "call_duration_min": 180,
    "is_unknown_number": 1,
    "is_video_call": 1,
    "hour_of_day": 10,
    "caller_call_history": 0,
    "outgoing_activity_ratio": 0.02,
    "day_of_week": 2
}
try:
    r = requests.post("http://localhost:8000/api/score", json=payload)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Risk Score: {data.get('risk_score')}")
        print(f"   Risk Level: {data.get('risk_level')}")
        print(f"   Top Factors: {data.get('top_factors')}")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: NGOs
print("\n4. Testing NGOs Endpoint...")
try:
    r = requests.get("http://localhost:8000/api/ngos/all")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Total NGOs: {data.get('total', 0)}")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*50)
print("✅ Test Complete!")