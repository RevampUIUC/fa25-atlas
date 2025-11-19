#!/usr/bin/env python3
"""
Test script for making outbound calls via the Atlas Voice Call API
"""
import requests
import json
import sys


API_BASE_URL = "http://localhost:8000"


def make_outbound_call(phone_number, user_id="test_user_001", script=None, recording=True):
    """
    Make an outbound call to a phone number

    Args:
        phone_number: Phone number in E.164 format (e.g., +18478345574)
        user_id: User identifier
        script: Custom message to speak during the call
        recording: Enable/disable call recording

    Returns:
        dict: Call response data
    """
    # Default script if none provided
    if script is None:
        script = (
            "Hello, this is a test call from the Atlas Voice Call system. "
            "This call is being made to verify the outbound calling functionality."
        )

    # Ensure phone number has + prefix
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    # Prepare request payload
    payload = {
        "to": phone_number,
        "user_external_id": user_id,
        "script": script,
        "recording_enabled": recording
    }

    # Make API request
    url = f"{API_BASE_URL}/calls/outbound"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        call_data = response.json()
        print("\n" + "="*60)
        print("CALL INITIATED SUCCESSFULLY!")
        print("="*60)
        print(f"Call ID:      {call_data.get('call_id')}")
        print(f"Twilio SID:   {call_data.get('twilio_sid')}")
        print(f"To Number:    {call_data.get('to_number')}")
        print(f"Status:       {call_data.get('status')}")
        print(f"Created At:   {call_data.get('created_at')}")
        print("="*60)
        print(f"\nThe phone should be ringing now at {phone_number}!")
        print(f"\nCheck call status with:")
        print(f"  curl http://localhost:8000/calls/{call_data.get('twilio_sid')}/debug")
        print("="*60 + "\n")

        return call_data

    except requests.exceptions.HTTPError as e:
        print(f"\nERROR: Call failed!")
        print(f"Status Code: {e.response.status_code}")
        try:
            error_data = e.response.json()
            print(f"Error Details: {json.dumps(error_data, indent=2)}")
        except:
            print(f"Error Details: {e.response.text}")
        sys.exit(1)

    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to API server!")
        print(f"Make sure the server is running at {API_BASE_URL}")
        sys.exit(1)

    except Exception as e:
        print(f"\nERROR: Unexpected error occurred: {str(e)}")
        sys.exit(1)


def get_call_status(twilio_sid):
    """Get the current status of a call"""
    url = f"{API_BASE_URL}/calls/{twilio_sid}/debug"

    try:
        response = requests.get(url)
        response.raise_for_status()
        call_data = response.json()

        print("\n" + "="*60)
        print("CALL STATUS")
        print("="*60)
        print(f"Call SID:     {call_data.get('call_sid')}")
        print(f"Status:       {call_data.get('status')}")
        print(f"To:           {call_data.get('to')}")
        print(f"Attempts:     {call_data.get('attempt_count')}")
        print(f"Should Retry: {call_data.get('should_retry')}")
        print("="*60 + "\n")

        return call_data

    except Exception as e:
        print(f"ERROR: Could not get call status: {str(e)}")
        sys.exit(1)


def main():
    """Main interactive function"""
    print("\n" + "="*60)
    print("ATLAS VOICE CALL TEST UTILITY")
    print("="*60 + "\n")

    # Get phone number
    if len(sys.argv) > 1:
        phone_number = sys.argv[1]
    else:
        phone_number = input("Enter phone number (e.g., 18478345574 or +18478345574): ").strip()

    if not phone_number:
        print("ERROR: Phone number is required!")
        sys.exit(1)

    # Optional: Get custom script
    use_custom = input("\nUse custom script? (y/n, default=n): ").strip().lower()
    script = None
    if use_custom == 'y':
        script = input("Enter your custom message: ").strip()

    # Optional: Recording
    recording_input = input("\nEnable call recording? (y/n, default=y): ").strip().lower()
    recording = recording_input != 'n'

    # Make the call
    print("\nInitiating call...")
    call_data = make_outbound_call(phone_number, script=script, recording=recording)

    # Ask if user wants to check status
    check_status = input("\nCheck call status? (y/n): ").strip().lower()
    if check_status == 'y':
        get_call_status(call_data.get('twilio_sid'))


if __name__ == "__main__":
    main()
