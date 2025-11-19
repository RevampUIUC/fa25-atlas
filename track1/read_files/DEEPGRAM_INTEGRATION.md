# Deepgram Real-Time Transcription Integration

This document describes the Deepgram integration for real-time speech-to-text transcription of Twilio calls.

## Overview

The integration provides:
- **Real-time transcription** of calls using Deepgram's streaming API
- **Automatic audio format handling** (Twilio's mulaw → Deepgram compatible)
- **WebSocket-based streaming** for low-latency transcription
- **Database storage** of transcripts linked to calls
- **Interim and final results** for responsive UX

## Architecture

```
Twilio Call → Media Stream (WebSocket) → FastAPI → Deepgram API
                                            ↓
                                        Database
                                     (transcripts)
```

### Components

1. **DeepgramSTTClient** ([app/deepgram_client.py](app/deepgram_client.py))
   - Manages Deepgram API authentication
   - Handles WebSocket connection to Deepgram
   - Processes transcription events
   - Supports callbacks for transcript and error handling

2. **TranscriptionSession** ([app/deepgram_client.py](app/deepgram_client.py))
   - Manages transcription for a single call
   - Stores transcripts to database
   - Tracks session state

3. **TwilioMediaStreamHandler** ([app/media_stream_handler.py](app/media_stream_handler.py))
   - Receives audio from Twilio via WebSocket
   - Forwards audio to Deepgram
   - Manages active transcription sessions

4. **WebSocket Endpoint** ([app/main.py](app/main.py))
   - `/twilio/stream` - Receives Twilio Media Streams

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies:
- `deepgram-sdk==3.2.7` - Deepgram Python SDK
- `websockets==12.0` - WebSocket support

### 2. Get Deepgram API Key

1. Sign up at [https://console.deepgram.com](https://console.deepgram.com)
2. Create a new API key
3. Copy the key

### 3. Configure Environment

Add to your `.env` file:

```bash
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

### 4. Test Connection

Run the test script:

```bash
python test_deepgram.py
```

Expected output:
```
============================================================
Deepgram Integration Test
============================================================

✓ API Key found: abc1234567...
✓ Deepgram client initialized successfully
Testing Deepgram connection...
✓ Successfully connected to Deepgram streaming API
✓ Connection closed successfully

============================================================
✅ Deepgram Integration Test PASSED
============================================================
```

## Usage

### Automatic Transcription

Transcription is **automatically enabled** for all outbound calls.

When a call is initiated:
1. TwiML includes `<Start><Stream>` directive
2. Twilio opens WebSocket to `/twilio/stream`
3. Audio is streamed in real-time
4. Deepgram transcribes audio
5. Transcripts saved to database

### Configuration Options

The Deepgram client supports various configuration options:

```python
await deepgram_client.start_transcription(
    language="en-US",           # Language code
    model="nova-2",              # Deepgram model
    punctuate=True,              # Add punctuation
    interim_results=True,        # Return interim results
    smart_format=True,           # Smart formatting
    utterance_end_ms=1000,       # Silence detection (ms)
)
```

#### Available Models

- `nova-2` - Latest, most accurate (recommended)
- `nova` - Previous generation
- `enhanced` - Enhanced accuracy
- `base` - Fastest, lower cost

#### Supported Languages

- `en-US` - English (US)
- `en-GB` - English (UK)
- `en-AU` - English (Australia)
- `es` - Spanish
- `fr` - French
- `de` - German
- And [many more](https://developers.deepgram.com/docs/languages)

### Audio Format

Twilio streams audio in **mulaw format**:
- **Encoding**: mulaw (μ-law)
- **Sample Rate**: 8000 Hz
- **Channels**: 1 (mono)
- **Bit Depth**: 8-bit

Deepgram automatically handles this format (no conversion needed).

### Database Schema

Transcripts are stored using the existing `save_transcript` method:

```python
db.save_transcript(
    call_sid="CA1234567890abcdef",  # Twilio call SID
    speaker="caller",                 # Speaker identifier
    text="Transcribed text here",    # Transcript text
    ts=datetime.utcnow()             # Timestamp
)
```

Stored in `transcripts` collection:
```json
{
  "call_sid": "CA1234567890abcdef",
  "speaker": "caller",
  "text": "Hello, I need help with my account",
  "ts": "2025-01-10T12:34:56.789Z",
  "created_at": "2025-01-10T12:34:56.789Z"
}
```

## How It Works

### Call Flow

```
1. Outbound Call Initiated
   POST /calls/outbound
   ↓
2. Twilio Calls Your Number
   ↓
3. Twilio Requests TwiML
   GET /twilio/voice?call_id=xxx&recording=true
   ↓
4. TwiML Response Includes Media Stream
   <Start>
     <Stream url="wss://yourapp.com/twilio/stream"/>
   </Start>
   ↓
5. Twilio Opens WebSocket
   WS /twilio/stream
   ↓
6. Audio Streamed in Real-Time
   {"event": "media", "media": {"payload": "base64_audio"}}
   ↓
7. Forwarded to Deepgram
   Deepgram WebSocket receives mulaw audio
   ↓
8. Transcription Results
   INTERIM: "Hello"
   INTERIM: "Hello, I need"
   FINAL: "Hello, I need help with my account."
   ↓
9. Saved to Database
   transcripts collection
```

### WebSocket Messages

#### From Twilio

```json
// Start event
{
  "event": "start",
  "streamSid": "MZ1234567890abcdef",
  "start": {
    "callSid": "CA1234567890abcdef",
    "streamSid": "MZ1234567890abcdef"
  }
}

// Media event (audio data)
{
  "event": "media",
  "streamSid": "MZ1234567890abcdef",
  "media": {
    "timestamp": "1641910800000",
    "payload": "base64_encoded_mulaw_audio"
  }
}

// Stop event
{
  "event": "stop",
  "streamSid": "MZ1234567890abcdef"
}
```

#### From Deepgram

Transcription results are processed via callbacks:

```python
def on_transcript(transcript: str, metadata: dict):
    # transcript: "Hello, I need help"
    # metadata: {
    #   "is_final": True,
    #   "speech_final": True,
    #   "confidence": 0.98,
    #   "duration": 2.5,
    #   "start": 0.0
    # }
```

## Logging

The integration provides detailed logging:

```
INFO - Deepgram client initialized successfully
INFO - Media stream handler initialized successfully
INFO - WebSocket connection accepted for call: CA123...
INFO - Media stream started - CallSid: CA123..., StreamSid: MZ456...
INFO - Deepgram WebSocket connection opened
INFO - Deepgram live transcription started: model=nova-2, language=en-US
INFO - Transcript [INTERIM]: Hello
INFO - Transcript [FINAL]: Hello, I need help with my account (confidence: 0.98)
INFO - Stored transcript for CA123...: Hello, I need help with my account
INFO - Media stream stopped - StreamSid: MZ456...
INFO - Transcription session stopped for call: CA123.... Total transcripts: 15
```

## Error Handling

### Common Errors

**1. Invalid API Key**
```
ERROR - Deepgram authentication error: Invalid API key
```
**Solution**: Check your `DEEPGRAM_API_KEY` in `.env`

**2. WebSocket Connection Failed**
```
ERROR - Failed to start Deepgram transcription: Connection refused
```
**Solution**: Check network connectivity and firewall settings

**3. Audio Format Mismatch**
```
WARNING - Deepgram returned error for audio chunk
```
**Solution**: Verify Twilio is sending mulaw-encoded audio

### Error Recovery

The integration includes automatic error recovery:
- WebSocket disconnections are logged but don't crash the server
- Failed transcriptions don't affect call recording
- Each call has an independent transcription session

## Performance

### Latency

- **Twilio → FastAPI**: ~50-100ms
- **FastAPI → Deepgram**: ~100-200ms
- **Deepgram Processing**: ~100-300ms
- **Total**: ~250-600ms end-to-end latency

### Throughput

- Handles multiple concurrent calls
- Each call has its own transcription session
- WebSocket connections are managed per session

### Cost Optimization

Deepgram pricing is based on audio duration:
- **Transcription**: ~$0.0043/minute (nova-2 model)
- **Streaming**: Real-time, no additional cost

To optimize costs:
- Use `base` model for less critical calls
- Disable `interim_results` if not needed
- Use `utterance_end_ms` to segment long silences

## Monitoring

### Active Sessions

Check active transcription sessions:

```python
count = media_stream_handler.get_active_sessions_count()
print(f"Active transcription sessions: {count}")
```

### Transcripts

Query transcripts for a call:

```python
transcripts = db.db.transcripts.find({"call_sid": "CA123..."})
for transcript in transcripts:
    print(f"{transcript['ts']}: {transcript['text']}")
```

## Troubleshooting

### No Transcripts Appearing

1. Check Deepgram API key is set
2. Verify WebSocket endpoint is accessible
3. Check logs for connection errors
4. Ensure BASE_URL is correct (ws:// or wss://)

### Low Transcription Accuracy

1. Check audio quality (ensure clear speech)
2. Try different Deepgram model (nova-2 vs base)
3. Verify language setting matches speaker
4. Check for background noise

### WebSocket Connection Drops

1. Check server WebSocket timeout settings
2. Verify network stability
3. Review Deepgram keepalive settings
4. Check firewall WebSocket policies

## API Reference

### DeepgramSTTClient

```python
client = DeepgramSTTClient(api_key="your_key")

# Start transcription
await client.start_transcription(
    on_transcript=callback_fn,
    on_error=error_fn,
    language="en-US",
    model="nova-2"
)

# Send audio
await client.send_audio(audio_bytes)

# Stop transcription
await client.stop_transcription()
```

### TranscriptionSession

```python
session = TranscriptionSession(
    call_sid="CA123",
    deepgram_client=client,
    db=database
)

# Start session
await session.start()

# Process audio
await session.process_audio(audio_data)

# Stop session
await session.stop()
```

## Security

- API keys stored in environment variables (not code)
- WebSocket connections use WSS in production
- Transcripts linked to calls for access control
- No audio stored (only transcripts)

## Future Enhancements

Potential improvements:
- **Speaker diarization** - Identify different speakers
- **Language detection** - Auto-detect language
- **Sentiment analysis** - Analyze transcript sentiment
- **Keyword detection** - Flag specific words/phrases
- **Real-time alerts** - Notify on transcript events
- **Custom vocabulary** - Add domain-specific terms

## Support

For issues or questions:
- Deepgram Docs: https://developers.deepgram.com
- Twilio Media Streams: https://www.twilio.com/docs/voice/media-streams
- GitHub Issues: [Your repo issues page]
