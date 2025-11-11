"""
Test script to validate webhook endpoints without actual Twilio calls
Tests /twilio/status and /twilio/recording endpoints
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_header(title):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_result(endpoint, status_code, response):
    """Print test result"""
    status_icon = "✅" if status_code == 200 else "❌"
    print(f"{status_icon} {endpoint}")
    print(f"   Status: {status_code}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    print()

def test_health():
    """Test health endpoint"""
    print_header("1. Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print_result("/health", response.status_code, response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

def test_status_webhook_initiated():
    """Test status webhook - initiated"""
    print_header("2. Status Webhook - Call Initiated")
    
    payload = {
        "CallSid": "CA1234567890abcdef1234567890abcdef",
        "CallStatus": "initiated",
        "To": "+15551234567",
        "From": "+15559876543",
        "Direction": "outbound-api",
        "ApiVersion": "2010-04-01",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "Timestamp": datetime.utcnow().isoformat()
    }
    
    print("📤 Sending payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/twilio/status",
            data=payload,
            timeout=5
        )
        print_result("/twilio/status (initiated)", response.status_code, response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Status webhook failed: {str(e)}")
        return False

def test_status_webhook_ringing():
    """Test status webhook - ringing"""
    print_header("3. Status Webhook - Call Ringing")
    
    payload = {
        "CallSid": "CA1234567890abcdef1234567890abcdef",
        "CallStatus": "ringing",
        "To": "+15551234567",
        "From": "+15559876543",
        "Direction": "outbound-api",
        "ApiVersion": "2010-04-01",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "Timestamp": datetime.utcnow().isoformat()
    }
    
    print("📤 Sending payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/twilio/status",
            data=payload,
            timeout=5
        )
        print_result("/twilio/status (ringing)", response.status_code, response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Status webhook failed: {str(e)}")
        return False

def test_status_webhook_in_progress():
    """Test status webhook - in-progress"""
    print_header("4. Status Webhook - Call In Progress")
    
    payload = {
        "CallSid": "CA1234567890abcdef1234567890abcdef",
        "CallStatus": "in-progress",
        "To": "+15551234567",
        "From": "+15559876543",
        "Direction": "outbound-api",
        "ApiVersion": "2010-04-01",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "Timestamp": datetime.utcnow().isoformat()
    }
    
    print("📤 Sending payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/twilio/status",
            data=payload,
            timeout=5
        )
        print_result("/twilio/status (in-progress)", response.status_code, response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Status webhook failed: {str(e)}")
        return False

def test_status_webhook_completed():
    """Test status webhook - completed"""
    print_header("5. Status Webhook - Call Completed")
    
    payload = {
        "CallSid": "CA1234567890abcdef1234567890abcdef",
        "CallStatus": "completed",
        "To": "+15551234567",
        "From": "+15559876543",
        "Direction": "outbound-api",
        "CallDuration": "45",
        "ApiVersion": "2010-04-01",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "Timestamp": datetime.utcnow().isoformat()
    }
    
    print("📤 Sending payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/twilio/status",
            data=payload,
            timeout=5
        )
        print_result("/twilio/status (completed)", response.status_code, response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Status webhook failed: {str(e)}")
        return False

def test_recording_webhook():
    """Test recording webhook"""
    print_header("6. Recording Webhook - Recording Completed")
    
    payload = {
        "RecordingSid": "RE1234567890abcdef1234567890abcdef",
        "RecordingUrl": "https://api.twilio.com/2010-04-01/Accounts/ACxxxx/Recordings/RExxxx",
        "RecordingStatus": "completed",
        "CallSid": "CA1234567890abcdef1234567890abcdef",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "ApiVersion": "2010-04-01",
        "RecordingDuration": "45",
        "TranscriptionText": "Hello, this is a test recording transcription."
    }
    
    print("📤 Sending payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/twilio/recording",
            data=payload,
            timeout=5
        )
        print_result("/twilio/recording", response.status_code, response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Recording webhook failed: {str(e)}")
        return False

def test_feedback_endpoints():
    """Test feedback submission and retrieval"""
    print_header("7. Feedback Endpoints")
    
    call_sid = "CA1234567890abcdef1234567890abcdef"
    
    # Test feedback submission
    feedback_payload = {
        "call_quality": 5,
        "agent_helpfulness": 4,
        "resolution": 5,
        "call_ease": 4,
        "overall_satisfaction": 5,
        "notes": "Great call experience!"
    }
    
    print("📤 Submitting feedback:")
    print(json.dumps(feedback_payload, indent=2))
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/calls/{call_sid}/feedback",
            json=feedback_payload,
            timeout=5
        )
        print_result(f"/calls/{call_sid}/feedback (POST)", response.status_code, response.json())
        
        # Test feedback retrieval
        print("\n📥 Retrieving feedback:")
        response = requests.get(f"{BASE_URL}/calls/{call_sid}/feedback", timeout=5)
        print_result(f"/calls/{call_sid}/feedback (GET)", response.status_code, response.json())
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Feedback test failed: {str(e)}")
        return False

def run_all_tests():
    """Run all webhook tests"""
    print("\n" + "=" * 70)
    print("  ATLAS WEBHOOK TESTING SUITE")
    print("  Testing without actual Twilio calls")
    print("=" * 70)
    print(f"\n🎯 Target: {BASE_URL}")
    print("⚠️  Make sure FastAPI is running on http://localhost:8000")
    print()
    
    input("Press Enter to start tests...")
    
    results = {
        "Health Check": test_health(),
        "Status - Initiated": test_status_webhook_initiated(),
        "Status - Ringing": test_status_webhook_ringing(),
        "Status - In Progress": test_status_webhook_in_progress(),
        "Status - Completed": test_status_webhook_completed(),
        "Recording Webhook": test_recording_webhook(),
        "Feedback Endpoints": test_feedback_endpoints(),
    }
    
    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, passed_test in results.items():
        icon = "✅" if passed_test else "❌"
        print(f"{icon} {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    run_all_tests()