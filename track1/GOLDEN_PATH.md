# Golden Path - Expected Results & Database Documents

## Overview
This document describes the expected behavior, JSON outputs, and MongoDB documents for the complete E2E flow.

---

## Complete Call Flow

### 1. Create User (Optional - Can use external_id directly)

**Endpoint:** `POST /users`

**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone_number": "+15551234567"
}
```

**Expected Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "phone_number": "+15551234567",
  "created_at": "2024-11-04T12:00:00Z",
  "updated_at": "2024-11-04T12:00:00Z"
}
```

**MongoDB Document (users collection):**
```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "name": "John Doe",
  "email": "john@example.com",
  "phone_number": "+15551234567",
  "external_id": "john_doe_ext_123",
  "phone": "+15551234567",
  "created_at": ISODate("2024-11-04T12:00:00Z"),
  "updated_at": ISODate("2024-11-04T12:00:00Z")
}
```

---

### 2. Initiate Outbound Call

**Endpoint:** `POST /calls/outbound`

**Request:**
```json
{
  "to": "+15551234567",
  "user_external_id": "507f1f77bcf86cd799439011",
  "script": "Hello! This is a test call from Atlas. If you hear this, everything is working!",
  "recording_enabled": true
}
```

**Expected Response:**
```json
{
  "call_id": "abc-123-def-456",
  "user_id": "507f1f77bcf86cd799439011",
  "to_number": "+15551234567",
  "status": "initiated",
  "created_at": "2024-11-04T12:00:00Z",
  "twilio_sid": "CA1234567890abcdef1234567890abcdef"
}
```

**What Happens:**
1. FastAPI generates unique `call_id` (UUID)
2. Calls `twilio_client.make_outbound_call()`
3. Twilio initiates the call
4. Call record saved to MongoDB
5. Response returned immediately (async)

**MongoDB Document (calls collection) - Initial:**
```json
{
  "_id": ObjectId("507f1f77bcf86cd799439012"),
  "call_id": "abc-123-def-456",
  "user_external_id": "507f1f77bcf86cd799439011",
  "user_id": "507f1f77bcf86cd799439011",
  "to_number": "+15551234567",
  "from_number": "+15559876543",
  "status": "initiated",
  "script": "Hello! This is a test call from Atlas.",
  "recording_enabled": true,
  "twilio_sid": "CA1234567890abcdef1234567890abcdef",
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "started_at": ISODate("2024-11-04T12:00:00Z"),
  "created_at": ISODate("2024-11-04T12:00:00Z"),
  "updated_at": ISODate("2024-11-04T12:00:00Z")
}
```

---

### 3. Webhook: Call Status - Initiated

**Twilio Sends:** `POST /twilio/status`

**Payload (Form Data):**
```
CallSid=CA1234567890abcdef1234567890abcdef
CallStatus=initiated
To=+15551234567
From=+15559876543
Direction=outbound-api
ApiVersion=2010-04-01
AccountSid=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Timestamp=Mon, 04 Nov 2024 12:00:00 +0000
```

**Expected Response:**
```json
{
  "status": "ok"
}
```

**What Happens:**
1. Endpoint receives webhook
2. Maps `CallStatus="initiated"` → `status="initiated"`
3. Updates call in MongoDB
4. Logs status change
5. Returns OK (always)

**MongoDB Update:**
```json
{
  "status": "initiated",
  "twilio_status": "initiated",
  "updated_at": ISODate("2024-11-04T12:00:00Z"),
  "meta": {
    "raw": {
      "To": "+15551234567",
      "From": "+15559876543",
      "Direction": "outbound-api",
      "CallStatus": "initiated"
    }
  }
}
```

---

### 4. Webhook: Call Status - Ringing

**Twilio Sends:** `POST /twilio/status`

**Payload:**
```
CallSid=CA1234567890abcdef1234567890abcdef
CallStatus=ringing
To=+15551234567
From=+15559876543
```

**MongoDB Update:**
```json
{
  "status": "ringing",
  "twilio_status": "ringing",
  "updated_at": ISODate("2024-11-04T12:00:05Z")
}
```

---

### 5. Webhook: Voice Instructions Request

**Twilio Sends:** `GET /twilio/voice?call_id=abc-123-def-456&recording=true`

**What Happens:**
1. Endpoint fetches call from MongoDB by `call_id`
2. Retrieves `script` from call document
3. Generates TwiML response

**Expected Response (TwiML XML):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">This call may be recorded for quality assurance and training purposes. By remaining on the line, you consent to this recording. If you do not consent, please hang up now.</Say>
  <Say voice="alice">Hello! This is a test call from Atlas. If you hear this, everything is working!</Say>
  <Record maxLength="3600" speechTimeout="5" trim="trim-silence" transcribe="true" transcribeCallback="https://your-ngrok-url/twilio/recording" recordingStatusCallback="https://your-ngrok-url/twilio/recording" recordingStatusCallbackMethod="POST"/>
  <Hangup/>
</Response>
```

**What Twilio Does:**
1. Plays consent message
2. Plays custom script
3. Starts recording
4. Hangs up after script

---

### 6. Webhook: Call Status - In Progress

**Twilio Sends:** `POST /twilio/status`

**Payload:**
```
CallSid=CA1234567890abcdef1234567890abcdef
CallStatus=in-progress
To=+15551234567
From=+15559876543
```

**MongoDB Update:**
```json
{
  "status": "in-progress",
  "twilio_status": "in-progress",
  "updated_at": ISODate("2024-11-04T12:00:10Z")
}
```

---

### 7. Webhook: Recording Completed

**Twilio Sends:** `POST /twilio/recording`

**Payload (Form Data):**
```
RecordingSid=RE1234567890abcdef1234567890abcdef
RecordingUrl=https://api.twilio.com/2010-04-01/Accounts/ACxxxx/Recordings/RExxxx
RecordingStatus=completed
RecordingDuration=45
CallSid=CA1234567890abcdef1234567890abcdef
AccountSid=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ApiVersion=2010-04-01
TranscriptionText=Hello, this is a test call from Atlas. If you hear this, everything is working!
```

**Expected Response:**
```json
{
  "status": "ok"
}
```

**What Happens:**
1. Finds call by `CallSid`
2. Creates recording document
3. Updates call with `recording_url`
4. Saves transcription text
5. Logs recording details

**MongoDB Document (recordings collection):**
```json
{
  "_id": ObjectId("507f1f77bcf86cd799439013"),
  "call_id": "507f1f77bcf86cd799439012",
  "twilio_sid": "RE1234567890abcdef1234567890abcdef",
  "recording_url": "https://api.twilio.com/2010-04-01/Accounts/ACxxxx/Recordings/RExxxx",
  "recording_status": "completed",
  "status": "completed",
  "duration": 45,
  "created_at": ISODate("2024-11-04T12:00:50Z")
}
```

**MongoDB Update (calls collection):**
```json
{
  "recording_url": "https://api.twilio.com/2010-04-01/Accounts/ACxxxx/Recordings/RExxxx",
  "transcription_text": "Hello, this is a test call from Atlas. If you hear this, everything is working!",
  "recording_saved_at": ISODate("2024-11-04T12:00:50Z"),
  "updated_at": ISODate("2024-11-04T12:00:50Z")
}
```

---

### 8. Webhook: Call Status - Completed

**Twilio Sends:** `POST /twilio/status`

**Payload:**
```
CallSid=CA1234567890abcdef1234567890abcdef
CallStatus=completed
To=+15551234567
From=+15559876543
CallDuration=45
```

**MongoDB Update:**
```json
{
  "status": "completed",
  "twilio_status": "completed",
  "duration_sec": 45,
  "ended_at": ISODate("2024-11-04T12:00:55Z"),
  "updated_at": ISODate("2024-11-04T12:00:55Z")
}
```

---

### 9. Submit Call Feedback

**Endpoint:** `POST /calls/CA1234567890abcdef1234567890abcdef/feedback`

**Request:**
```json
{
  "call_quality": 5,
  "agent_helpfulness": 4,
  "resolution": 5,
  "call_ease": 4,
  "overall_satisfaction": 5,
  "notes": "Great call experience! Everything worked perfectly."
}
```

**Expected Response:**
```json
{
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "call_quality": 5,
  "agent_helpfulness": 4,
  "resolution": 5,
  "call_ease": 4,
  "overall_satisfaction": 5,
  "notes": "Great call experience! Everything worked perfectly.",
  "created_at": "2024-11-04T12:05:00Z"
}
```

**MongoDB Update (calls collection):**
```json
{
  "feedback": {
    "call_quality": 5,
    "agent_helpfulness": 4,
    "resolution": 5,
    "call_ease": 4,
    "overall_satisfaction": 5,
    "notes": "Great call experience! Everything worked perfectly.",
    "feedback_provided_at": ISODate("2024-11-04T12:05:00Z")
  },
  "updated_at": ISODate("2024-11-04T12:05:00Z")
}
```

---

### 10. Retrieve Call Feedback

**Endpoint:** `GET /calls/CA1234567890abcdef1234567890abcdef/feedback`

**Expected Response:**
```json
{
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "call_quality": 5,
  "agent_helpfulness": 4,
  "resolution": 5,
  "call_ease": 4,
  "overall_satisfaction": 5,
  "notes": "Great call experience! Everything worked perfectly.",
  "created_at": "2024-11-04T12:05:00Z"
}
```

---

## Final MongoDB Documents

### calls Collection - Complete Document

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439012"),
  "call_id": "abc-123-def-456",
  "user_external_id": "507f1f77bcf86cd799439011",
  "user_id": "507f1f77bcf86cd799439011",
  "to_number": "+15551234567",
  "from_number": "+15559876543",
  "status": "completed",
  "twilio_status": "completed",
  "script": "Hello! This is a test call from Atlas. If you hear this, everything is working!",
  "recording_enabled": true,
  "twilio_sid": "CA1234567890abcdef1234567890abcdef",
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "recording_url": "https://api.twilio.com/2010-04-01/Accounts/ACxxxx/Recordings/RExxxx",
  "transcription_text": "Hello, this is a test call from Atlas. If you hear this, everything is working!",
  "duration_sec": 45,
  "started_at": ISODate("2024-11-04T12:00:00Z"),
  "ended_at": ISODate("2024-11-04T12:00:55Z"),
  "recording_saved_at": ISODate("2024-11-04T12:00:50Z"),
  "created_at": ISODate("2024-11-04T12:00:00Z"),
  "updated_at": ISODate("2024-11-04T12:05:00Z"),
  "direction": "outbound-api",
  "meta": {
    "raw": {
      "To": "+15551234567",
      "From": "+15559876543",
      "Direction": "outbound-api",
      "ApiVersion": "2010-04-01",
      "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "Timestamp": "Mon, 04 Nov 2024 12:00:55 +0000",
      "CallStatus": "completed"
    }
  },
  "feedback": {
    "call_quality": 5,
    "agent_helpfulness": 4,
    "resolution": 5,
    "call_ease": 4,
    "overall_satisfaction": 5,
    "notes": "Great call experience! Everything worked perfectly.",
    "feedback_provided_at": ISODate("2024-11-04T12:05:00Z")
  }
}
```

---

## Database Schema Reference

### users Collection
```javascript
{
  _id: ObjectId,
  name: String,
  email: String (unique),
  phone_number: String,
  external_id: String (unique),
  phone: String,
  created_at: ISODate,
  updated_at: ISODate
}
```

### calls Collection
```javascript
{
  _id: ObjectId,
  call_id: String (UUID),
  user_external_id: String,
  user_id: String,
  to_number: String,
  from_number: String,
  status: String (initiated|ringing|in-progress|completed|failed|busy|no-answer),
  twilio_status: String,
  script: String,
  recording_enabled: Boolean,
  twilio_sid: String (unique),
  call_sid: String (unique),
  recording_url: String (optional),
  transcription_text: String (optional),
  duration_sec: Integer (optional),
  started_at: ISODate,
  ended_at: ISODate (optional),
  recording_saved_at: ISODate (optional),
  created_at: ISODate,
  updated_at: ISODate,
  direction: String,
  meta: Object,
  feedback: {
    call_quality: Integer (1-5),
    agent_helpfulness: Integer (1-5),
    resolution: Integer (1-5),
    call_ease: Integer (1-5),
    overall_satisfaction: Integer (1-5),
    notes: String (optional),
    feedback_provided_at: ISODate
  }
}
```

### recordings Collection
```javascript
{
  _id: ObjectId,
  call_id: String,
  twilio_sid: String,
  recording_url: String,
  recording_status: String,
  status: String,
  duration: Integer,
  created_at: ISODate
}
```

### transcripts Collection
```javascript
{
  _id: ObjectId,
  call_sid: String,
  speaker: String,
  text: String,
  ts: ISODate,
  created_at: ISODate
}
```

---

## Testing Checklist

- [ ] Health check returns "healthy" status
- [ ] Outbound call creates call record in MongoDB
- [ ] Status webhook (initiated) updates call status
- [ ] Status webhook (ringing) updates call status
- [ ] Voice webhook returns valid TwiML
- [ ] Status webhook (in-progress) updates call status
- [ ] Recording webhook creates recording document
- [ ] Recording webhook updates call with recording_url
- [ ] Status webhook (completed) marks call as completed
- [ ] Feedback submission saves to call document
- [ ] Feedback retrieval returns saved feedback
- [ ] All timestamps are UTC
- [ ] All MongoDB indexes exist

---

## Notes for Swarnika (Database Testing)

1. Use `mock_payloads.json` to simulate webhooks
2. Expected documents are shown above
3. Key indexes to verify:
   - `users.external_id` (unique)
   - `calls.call_sid` (unique)
   - `calls.user_id` + `calls.started_at`
4. Feedback is embedded in calls collection
5. Transcription text stored in both calls and potentially transcripts collection