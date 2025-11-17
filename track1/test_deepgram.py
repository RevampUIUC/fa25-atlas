#!/usr/bin/env python3
"""
Test script for Deepgram integration
Verifies API authentication and basic configuration
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.deepgram_client import DeepgramSTTClient


async def test_deepgram_authentication():
    """Test Deepgram API authentication"""
    print("=" * 60)
    print("Deepgram Integration Test")
    print("=" * 60)
    print()

    # Check API key
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key or api_key == "your_deepgram_api_key_here":
        print("❌ DEEPGRAM_API_KEY not set in .env file")
        print()
        print("Please set your Deepgram API key:")
        print("1. Sign up at https://console.deepgram.com")
        print("2. Create an API key")
        print("3. Add it to your .env file:")
        print("   DEEPGRAM_API_KEY=your_actual_api_key")
        print()
        return False

    print(f"✓ API Key found: {api_key[:10]}..." + "*" * 20)
    print()

    # Initialize client
    try:
        client = DeepgramSTTClient(api_key=api_key)
        print("✓ Deepgram client initialized successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize Deepgram client: {str(e)}")
        return False

    # Test callback
    transcripts_received = []

    def on_transcript(transcript: str, metadata: dict):
        """Handle transcript callback"""
        status = "FINAL" if metadata.get("is_final") else "INTERIM"
        confidence = metadata.get("confidence", 0)
        print(f"[{status}] Transcript: {transcript} (confidence: {confidence:.2f})")
        transcripts_received.append(transcript)

    def on_error(error: str):
        """Handle error callback"""
        print(f"Error: {error}")

    # Test connection (quick test without actual audio)
    print("Testing Deepgram connection...")
    try:
        # Note: This will create a connection but we won't send audio
        # In production, audio would be streamed from Twilio
        await client.start_transcription(
            on_transcript=on_transcript,
            on_error=on_error,
            language="en-US",
            model="nova-2",
            punctuate=True,
            interim_results=True,
        )
        print("✓ Successfully connected to Deepgram streaming API")
        print()

        # Wait a moment then close
        await asyncio.sleep(1)
        await client.stop_transcription()
        print("✓ Connection closed successfully")
        print()

    except Exception as e:
        print(f"❌ Connection test failed: {str(e)}")
        print()
        print("Common issues:")
        print("- Invalid API key")
        print("- Network connectivity issues")
        print("- Firewall blocking WebSocket connections")
        return False

    print("=" * 60)
    print("✅ Deepgram Integration Test PASSED")
    print("=" * 60)
    print()
    print("Configuration Summary:")
    print(f"  - Model: nova-2")
    print(f"  - Language: en-US")
    print(f"  - Encoding: mulaw (8kHz, mono)")
    print(f"  - Punctuation: Enabled")
    print(f"  - Smart Format: Enabled")
    print()
    print("Next steps:")
    print("1. Start your FastAPI server: uvicorn app.main:app --reload")
    print("2. Make a test call through Twilio")
    print("3. Check logs for real-time transcription output")
    print()

    return True


async def test_database_connection():
    """Test database connection for transcription storage"""
    print("Testing database connection for transcription storage...")

    try:
        from app.dao import MongoDatabase

        db = MongoDatabase(
            connection_string=os.getenv("MONGO_URI"),
            database_name=os.getenv("MONGO_DB", "atlas"),
        )

        # Test save_transcript method
        from datetime import datetime
        test_call_sid = "TEST_CALL_SID_" + str(datetime.now().timestamp())

        db.save_transcript(
            call_sid=test_call_sid,
            speaker="test",
            text="This is a test transcription",
            ts=datetime.utcnow()
        )

        print("✓ Database connection successful")
        print("✓ Transcription storage working")
        print()

        return True

    except Exception as e:
        print(f"❌ Database test failed: {str(e)}")
        print()
        return False


if __name__ == "__main__":
    async def main():
        """Run all tests"""
        success = await test_deepgram_authentication()

        if success:
            await test_database_connection()

        return success

    # Run tests
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
