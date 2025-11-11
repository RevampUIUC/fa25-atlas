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

- Python 3.8+
- MongoDB (local or Atlas)
- Twilio account with credits
- pip

### Setup Steps

1. **Navigate to the project**
   ```bash
   cd track1
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Edit `.env` with your credentials:
     ```bash
     # Twilio
     TWILIO_ACCOUNT_SID=your_account_sid
     TWILIO_AUTH_TOKEN=your_auth_token
     TWILIO_FROM_NUMBER=+1234567890

     # MongoDB
     MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/atlas

     # Application
     BASE_URL=http://localhost:8000
     ```

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

### 1. Create a User

```bash
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone_number": "+1234567890"
  }'
```

### 2. Initiate an Outbound Call

```bash
curl -X POST "http://localhost:8000/calls/outbound" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_id_from_create",
    "to_number": "+1987654321",
    "script": "Hello, this is a test call.",
    "recording_enabled": true
  }'
```

### 3. List User Calls

```bash
curl "http://localhost:8000/users/{user_id}/calls?page=1&page_size=10"
```

### 4. Health Check

```bash
curl "http://localhost:8000/health"
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| ENVIRONMENT | App environment | development, production |
| HOST | Server host | 0.0.0.0 |
| PORT | Server port | 8000 |
| TWILIO_ACCOUNT_SID | Twilio account ID | ACxxxxxxxxx |
| TWILIO_AUTH_TOKEN | Twilio auth token | xxxxxxxxxxxx |
| TWILIO_FROM_NUMBER | Outbound call number | +1234567890 |
| MONGO_URI | MongoDB connection string | mongodb://localhost:27017 |
| MONGO_DB | Database name | atlas |
| BASE_URL | Application base URL | http://localhost:8000 |
| LOG_LEVEL | Logging level | INFO, DEBUG |

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

### Retries & Logging (Track 1)
- Env:
  - RETRY_LIMIT (default 3)
  - RETRY_DELAY (seconds, default 10)
- Every status update to `/twilio/status` appends an entry to `calls.attempts[]` and increments `attempt_count`.
- Fields added on `calls`:
  - attempts: [{ attempt_no, status, reason, at }]
  - attempt_count, retry_limit, retry_delay_sec

