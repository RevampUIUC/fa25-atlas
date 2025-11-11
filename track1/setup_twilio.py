import os
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_twilio_webhooks():
    """Configure Twilio webhooks automatically"""
    
    # Get credentials from .env
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    base_url = os.getenv("BASE_URL")
    
    # Validate configuration
    if not all([account_sid, auth_token, from_number, base_url]):
        print("❌ Missing required environment variables!")
        print("Required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, BASE_URL")
        return False
    
    if "localhost" in base_url or "127.0.0.1" in base_url:
        print("❌ BASE_URL is still set to localhost!")
        print("Please update BASE_URL in .env to your ngrok URL")
        return False
    
    print(f"🔧 Configuring Twilio webhooks...")
    print(f"   Account SID: {account_sid[:10]}...")
    print(f"   Phone Number: {from_number}")
    print(f"   Base URL: {base_url}")
    
    try:
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Find the phone number
        incoming_phone_numbers = client.incoming_phone_numbers.list(
            phone_number=from_number
        )
        
        if not incoming_phone_numbers:
            print(f"❌ Phone number {from_number} not found in your Twilio account")
            print("\n📋 Available numbers in your account:")
            all_numbers = client.incoming_phone_numbers.list()
            for num in all_numbers:
                print(f"   - {num.phone_number}")
            return False
        
        phone_number_sid = incoming_phone_numbers[0].sid
        
        # Configure webhooks
        voice_url = f"{base_url}/twilio/voice"
        status_callback_url = f"{base_url}/twilio/status"
        
        client.incoming_phone_numbers(phone_number_sid).update(
            voice_url=voice_url,
            voice_method="POST",
            status_callback=status_callback_url,
            status_callback_method="POST",
        )
        
        print(f"\n✅ Webhooks configured successfully!")
        print(f"\n📞 Voice Webhook:")
        print(f"   URL: {voice_url}")
        print(f"   Method: POST")
        print(f"\n📊 Status Callback:")
        print(f"   URL: {status_callback_url}")
        print(f"   Method: POST")
        print(f"\n🎙️ Recording Callback (auto-configured in code):")
        print(f"   URL: {base_url}/twilio/recording")
        print(f"   Method: POST")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error configuring webhooks: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Twilio Webhook Configuration Setup")
    print("=" * 60)
    setup_twilio_webhooks()