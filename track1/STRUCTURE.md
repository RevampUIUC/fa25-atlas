# Project Structure Overview

## Directory Layout

```
track1/
├── app/
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # Main FastAPI application with all endpoints
│   ├── models.py                # Pydantic request/response models
│   ├── dao.py                   # MongoDB data access layer
│   └── twilio_client.py          # Twilio API client wrapper
├── .env                          # Environment variables (create your own)
├── .gitignore                    # Git ignore rules
├── .venv/                        # Virtual environment (do not commit)
├── requirements.txt              # Python package dependencies
├── readme.md                     # Full documentation
├── QUICKSTART.md                 # Quick start guide
└── STRUCTURE.md                  # This file
```

## File Descriptions

### app/main.py
The core FastAPI application containing:
- **Startup/Shutdown Events**: Initialize MongoDB and Twilio clients
- **Health Check** (`GET /health`): Verify database and Twilio connectivity
- **User Endpoints**:
  - `POST /users` - Create new user
  - `GET /users` - List users with pagination
  - `GET /users/{user_id}` - Get specific user
  - `GET /users/{user_id}/calls` - List user's calls
- **Call Endpoints**:
  - `POST /calls/outbound` - Initiate outbound call
- **Webhook Endpoints**:
  - `POST /twilio/voice` - Handle voice requests, return TwiML
  - `POST /twilio/status` - Handle call status updates
  - `POST /twilio/recording` - Handle recording completion
- **Error Handlers**: Custom exception handlers for HTTP and general errors

### app/models.py
Pydantic models for request/response validation:

**Enums:**
- `CallStatus` - Call state: initiated, ringing, in-progress, completed, failed, no-answer, busy
- `RecordingStatus` - Recording state: processing, completed, failed

**Request Models:**
- `UserCreate` - User creation request (name, email, phone_number)
- `OutboundCallRequest` - Outbound call request (user_id, to_number, script, recording_enabled)
- `TwilioWebhookRequest` - Twilio webhook data
- `RecordingWebhookRequest` - Recording webhook data

**Response Models:**
- `User` - User with id, timestamps
- `OutboundCallResponse` - Call with id, status, timestamps
- `HealthResponse` - Health check with database and Twilio status
- `ErrorResponse` - Error details with timestamp
- `CallListResponse` - Paginated calls list

### app/dao.py
MongoDB data access layer with methods for:

**Users:**
- `create_user(user_data)` - Insert new user
- `get_user(user_id)` - Fetch user by ID
- `get_user_by_email(email)` - Fetch user by email
- `list_users(page, page_size)` - Paginated user list
- `update_user(user_id, update_data)` - Update user fields
- `delete_user(user_id)` - Delete user

**Calls:**
- `create_call(call_data)` - Insert new call record
- `get_call(call_id)` - Fetch call by ID
- `get_call_by_twilio_sid(twilio_sid)` - Fetch call by Twilio SID
- `list_user_calls(user_id, page, page_size)` - Paginated user calls
- `update_call(call_id, update_data)` - Update call record
- `update_call_by_twilio_sid(twilio_sid, update_data)` - Update via Twilio SID

**Recordings:**
- `create_recording(recording_data)` - Insert recording record
- `get_recording(recording_id)` - Fetch recording by ID
- `get_recording_by_call_id(call_id)` - Fetch recording for call
- `update_recording(recording_id, update_data)` - Update recording
- `list_call_recordings(call_id)` - List recordings for call

**Indexes:** Automatically creates indexes on:
- `users.email` (unique)
- `users.phone_number`
- `calls.user_id`
- `calls.twilio_sid` (unique)
- `calls.created_at`
- `calls.status`
- `recordings.call_id`
- `recordings.twilio_sid`

### app/twilio_client.py
Twilio API wrapper with methods for:
- `make_outbound_call(to_number, call_id, script, recording_enabled)` - Initiate call
- `get_call_details(call_sid)` - Fetch call details
- `generate_twiml_response(script, record_call)` - Generate TwiML for voice
- `get_recording_url(recording_sid)` - Get recording URL and transcription
- `hangup_call(call_sid)` - Terminate call

Features:
- Automatic webhook callback setup
- TwiML generation with recording
- Call status tracking
- Error handling and logging

### .env
Environment configuration file (create by copying template):
```
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1234567890
MONGO_URI=mongodb://localhost:27017/atlas
MONGO_DB=atlas
BASE_URL=http://localhost:8000
LOG_LEVEL=INFO
```

### requirements.txt
Python dependencies organized by category:
- **Web Framework**: FastAPI, Uvicorn, Pydantic
- **Twilio**: twilio SDK
- **Database**: pymongo, motor
- **Configuration**: python-dotenv
- **Development**: pytest, black, flake8, mypy

## Database Collections

### users
```json
{
  "_id": ObjectId,
  "name": "string",
  "email": "string (unique)",
  "phone_number": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### calls
```json
{
  "_id": ObjectId,
  "call_id": "string (UUID)",
  "user_id": "string (MongoDB ObjectId)",
  "twilio_sid": "string (unique)",
  "to_number": "string",
  "from_number": "string",
  "status": "string (enum)",
  "script": "string",
  "recording_enabled": "boolean",
  "recording_url": "string (optional)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### recordings
```json
{
  "_id": ObjectId,
  "call_id": "string (MongoDB ObjectId)",
  "twilio_sid": "string (unique)",
  "recording_url": "string",
  "recording_status": "string",
  "status": "string (enum)",
  "created_at": "datetime"
}
```

## Data Flow

### Creating an Outbound Call

1. User sends POST `/calls/outbound` with user_id, to_number, script, recording_enabled
2. App verifies user exists in MongoDB
3. App generates unique call_id (UUID)
4. Twilio client initiates call with voice_url pointing to `/twilio/voice`
5. Twilio SID returned and stored in database
6. Call status set to "initiated"

### Handling Call Status

1. Twilio calls `/twilio/status` webhook with CallSid and status
2. App retrieves call record using Twilio SID
3. App maps Twilio status to app status
4. Database call record updated with new status
5. Returns 200 OK to Twilio

### Handling Recording

1. Call completes and Twilio records audio
2. Twilio calls `/twilio/recording` webhook with RecordingSid, RecordingUrl
3. App retrieves associated call record
4. Recording record created in database with URL
5. Call record updated with recording_url
6. Returns 200 OK to Twilio

## Security Features

- Input validation via Pydantic models
- MongoDB connection with authentication support
- Twilio credentials in environment variables
- Error responses don't leak sensitive information
- CORS enabled for development

## Performance Features

- Database indexes for fast queries
- Pagination support for list endpoints
- Efficient Twilio API calls
- Async/await compatible (FastAPI)
- Connection pooling ready (Motor support)

## Logging

All modules have logging configured:
- File: `app/main.py`, `app/dao.py`, `app/twilio_client.py`
- Level: INFO (configurable via LOG_LEVEL)
- Format: Timestamp, module name, log level, message

## Error Handling

- HTTP exceptions return proper status codes
- Validation errors from Pydantic models
- Database operations wrapped in try-catch
- Twilio errors logged and re-raised
- Webhook errors logged but return 200 OK to prevent retries
