# Atlas - Twilio Call Management API

A FastAPI-based application for managing outbound calls and recordings using Twilio integration with MongoDB for persistence.

## Features

- **User Management**: Create and manage users with email and phone numbers
- **Outbound Calls**: Initiate outbound calls via Twilio with custom scripts
- **Call Recording**: Automatic call recording with webhook handling
- **Call Status Tracking**: Real-time call status updates from Twilio webhooks
- **MongoDB Integration**: Persistent storage for users, calls, and recordings
- **RESTful API**: Full OpenAPI/Swagger documentation

## Project Structure

```
track1/
├── app/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # FastAPI application and endpoints
│   ├── models.py             # Pydantic models for requests/responses
│   ├── dao.py                # MongoDB data access layer
│   └── twilio_client.py       # Twilio API wrapper
├── .env                       # Environment configuration
├── requirements.txt           # Python dependencies
└── readme.md                  # This file
```

## Installation

### Prerequisites

- **Python** 3.8 or higher
- **MongoDB** (local instance or MongoDB Atlas cloud)
- **Twilio Account** with phone number and credits
- **pip** package manager
- **Virtual Environment** tool (venv)

### Quick Setup

1. **Clone and navigate to the project**
   ```bash
   cd fa25-atlas/track1
   ```

2. **Create and activate virtual environment**
   ```bash
   # Linux/Mac
   python -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create and configure `.env` file**
   ```bash
   cp .env.example .env  # Or create manually
   ```

   Edit `.env` with your credentials:
   ```env
   # Application Environment
   ENVIRONMENT=development
   HOST=0.0.0.0
   PORT=8000

   # Twilio Configuration
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_FROM_NUMBER=+1234567890

   # MongoDB Configuration
   MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   MONGO_DB=atlas

   # Application URLs
   BASE_URL=http://localhost:8000

   # Logging
   LOG_LEVEL=INFO
   ```

5. **Verify MongoDB connection**
   ```bash
   # Test MongoDB connectivity (optional)
   # Ensure MongoDB is running and accessible
   ```

6. **Run the application**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

   The API will be available at: `http://localhost:8000`
   Swagger documentation: `http://localhost:8000/docs`
   ReDoc documentation: `http://localhost:8000/redoc`

## API Endpoints

### Health & Status
- **GET** `/health` - Health check endpoint
- **GET** `/` - Root endpoint with API info

### User Management
- **GET** `/users` - List all users (paginated)
- **GET** `/users/{user_id}` - Get specific user
- **POST** `/users` - Create new user
- **GET** `/users/{user_id}/calls` - List user's calls

### Calls
- **POST** `/calls/outbound` - Initiate outbound call

### Twilio Webhooks
- **POST** `/twilio/voice` - Handle voice requests (TwiML response)
- **POST** `/twilio/status` - Handle call status updates
- **POST** `/twilio/recording` - Handle recording completion

## Running the Application

### Development

```bash
python -m uvicorn app.main:app --reload
```

Access the API at: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### Production

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
```

## API Usage Examples

### Setup for Examples

Store your call SID from a previous call creation. Replace placeholders:
- `{user_id}` - User ID from create user response
- `{call_sid}` - Twilio Call SID (starts with `CA`)
- `http://localhost:8000` - Your API base URL

### 1. Create a User

**curl:**
```bash
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "email": "jane.smith@example.com",
    "phone_number": "+14155551234"
  }'
```

**Postman:**
- Method: `POST`
- URL: `http://localhost:8000/users`
- Header: `Content-Type: application/json`
- Body (raw JSON):
```json
{
  "name": "Jane Smith",
  "email": "jane.smith@example.com",
  "phone_number": "+14155551234"
}
```

### 2. Initiate an Outbound Call

**curl:**
```bash
curl -X POST "http://localhost:8000/calls/outbound" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+14155559876",
    "user_external_id": "ext_user_123",
    "script": "Hello, this is a test call from Atlas.",
    "recording_enabled": true
  }'
```

**Postman:**
- Method: `POST`
- URL: `http://localhost:8000/calls/outbound`
- Header: `Content-Type: application/json`
- Body (raw JSON):
```json
{
  "to": "+14155559876",
  "user_external_id": "ext_user_123",
  "script": "Hello, this is a test call from Atlas.",
  "recording_enabled": true
}
```

### 3. Submit Call Feedback (NEW)

**curl:**
```bash
curl -X PATCH "http://localhost:8000/calls/{call_sid}/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "call_quality": 4,
    "agent_helpfulness": 5,
    "resolution": 3,
    "call_ease": 4,
    "overall_satisfaction": 4,
    "notes": "Agent was helpful but took a while to resolve the issue."
  }'
```

**Postman:**
- Method: `PATCH`
- URL: `http://localhost:8000/calls/{call_sid}/feedback`
- Header: `Content-Type: application/json`
- Body (raw JSON):
```json
{
  "call_quality": 4,
  "agent_helpfulness": 5,
  "resolution": 3,
  "call_ease": 4,
  "overall_satisfaction": 4,
  "notes": "Agent was helpful but took a while to resolve the issue."
}
```

**Expected Response (200 OK):**
```json
{
  "call_sid": "CA1234567890abcdef1234567890abcdef",
  "call_quality": 4,
  "agent_helpfulness": 5,
  "resolution": 3,
  "call_ease": 4,
  "overall_satisfaction": 4,
  "notes": "Agent was helpful but took a while to resolve the issue.",
  "created_at": "2025-11-03T15:45:30.123456"
}
```

### 4. Retrieve Call Feedback (NEW)

**curl:**
```bash
curl -X GET "http://localhost:8000/calls/{call_sid}/feedback" \
  -H "Content-Type: application/json"
```

**Postman:**
- Method: `GET`
- URL: `http://localhost:8000/calls/{call_sid}/feedback`

### 5. List User Calls

**curl:**
```bash
curl -X GET "http://localhost:8000/users/{user_id}/calls?page=1&page_size=10" \
  -H "Content-Type: application/json"
```

**Postman:**
- Method: `GET`
- URL: `http://localhost:8000/users/{user_id}/calls?page=1&page_size=10`

### 6. Health Check

**curl:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Postman:**
- Method: `GET`
- URL: `http://localhost:8000/health`

## Error Handling Examples

### 400 Bad Request - Invalid Feedback Scores

**curl:**
```bash
curl -X PATCH "http://localhost:8000/calls/{call_sid}/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "call_quality": 6,
    "agent_helpfulness": 5,
    "resolution": 3,
    "call_ease": 4,
    "overall_satisfaction": 4
  }'
```

**Response (400):**
```json
{
  "detail": "Invalid call_quality: must be an integer between 1 and 5"
}
```

### 404 Not Found - Call Not Found

**curl:**
```bash
curl -X GET "http://localhost:8000/calls/INVALID_SID/feedback"
```

**Response (404):**
```json
{
  "detail": "Call not found: INVALID_SID"
}
```

### 404 Not Found - No Feedback for Call

**curl:**
```bash
curl -X GET "http://localhost:8000/calls/{call_sid}/feedback"
```

**Response (404):**
```json
{
  "detail": "No feedback found for call: {call_sid}"
}
```

### 500 Internal Server Error

**Response (500):**
```json
{
  "detail": "Internal server error: unexpected error occurred"
}
```

Check application logs for detailed error messages.

## Environment Variables

### Required Variables

| Variable | Description | Example | Notes |
|----------|-------------|---------|-------|
| **TWILIO_ACCOUNT_SID** | Twilio Account SID | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | Find in Twilio Console |
| **TWILIO_AUTH_TOKEN** | Twilio Authentication Token | `your_auth_token_here` | Find in Twilio Console |
| **TWILIO_FROM_NUMBER** | Outbound phone number | `+14155552671` | Verified Twilio phone number |
| **MONGO_URI** | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority` | MongoDB Atlas or local |
| **BASE_URL** | Application webhook base URL | `http://localhost:8000` | For local: `http://localhost:8000`; For production: your domain |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| ENVIRONMENT | Application environment | `development` | `development` or `production` |
| HOST | Server host | `0.0.0.0` | `0.0.0.0`, `127.0.0.1` |
| PORT | Server port | `8000` | `8000`, `5000` |
| MONGO_DB | MongoDB database name | `atlas` | `atlas`, `atlas_dev` |
| LOG_LEVEL | Logging verbosity | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### How to Get Twilio Credentials

1. Go to [Twilio Console](https://www.twilio.com/console)
2. Look for **Account SID** and **Auth Token** on the main dashboard
3. In **Phone Numbers > Manage Numbers**, get your verified phone number for `TWILIO_FROM_NUMBER`

### How to Set Up MongoDB

**Local MongoDB:**
```env
MONGO_URI=mongodb://localhost:27017
```

**MongoDB Atlas (Cloud):**
1. Create cluster at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create database user with password
3. Whitelist your IP address
4. Copy connection string:
```env
MONGO_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

## Testing

```bash
pytest
```

## Error Handling

The API returns standard HTTP status codes:
- **200** - Success
- **201** - Created
- **400** - Bad Request
- **404** - Not Found
- **409** - Conflict (e.g., duplicate email)
- **500** - Internal Server Error

## Logging

Logs are written to console with timestamps and log levels. Configure via LOG_LEVEL environment variable.

## Security Considerations

- Store `.env` securely and never commit to version control
- Use HTTPS in production
- Validate all incoming requests
- Implement rate limiting for production
- Use MongoDB connection string with authentication
