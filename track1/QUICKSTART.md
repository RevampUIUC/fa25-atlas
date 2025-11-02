# Quick Start Guide

## Prerequisites
- Python 3.8+
- MongoDB running (local or cloud)
- Twilio account

## 1. Setup

```bash
# Activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure Environment

Edit `.env` file with your credentials:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890
MONGO_URI=mongodb://localhost:27017/atlas
BASE_URL=http://localhost:8000
```

## 3. Run the Application

```bash
python -m uvicorn app.main:app --reload
```

Server starts at `http://localhost:8000`

## 4. Access API Documentation

Open `http://localhost:8000/docs` in your browser for interactive Swagger UI

## 5. Basic API Flow

### Step 1: Create a User
```bash
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "phone_number": "+15551234567"
  }'
```

Copy the returned `id` field.

### Step 2: Make an Outbound Call
```bash
curl -X POST "http://localhost:8000/calls/outbound" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "PASTE_USER_ID_HERE",
    "to_number": "+15559876543",
    "script": "Hello, this is a test call.",
    "recording_enabled": true
  }'
```

### Step 3: Check Call Status
```bash
curl "http://localhost:8000/users/PASTE_USER_ID_HERE/calls"
```

## 6. File Descriptions

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application with all endpoints |
| `app/models.py` | Pydantic models for data validation |
| `app/dao.py` | MongoDB data access layer |
| `app/twilio_client.py` | Twilio API wrapper |
| `.env` | Environment configuration (create your own) |
| `requirements.txt` | Python dependencies |

## 7. Available Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /users` - Create user
- `GET /users` - List users
- `GET /users/{user_id}` - Get user
- `POST /calls/outbound` - Make outbound call
- `GET /users/{user_id}/calls` - List user calls
- `POST /twilio/voice` - Voice webhook (auto)
- `POST /twilio/status` - Status webhook (auto)
- `POST /twilio/recording` - Recording webhook (auto)

## 8. Troubleshooting

### MongoDB Connection Error
```
Error: Failed to connect to MongoDB
```
- Ensure MongoDB is running: `mongod` (local) or check Atlas connection string
- Verify MONGO_URI in `.env`

### Twilio Error
```
Error: Missing required Twilio configuration
```
- Check TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in `.env`
- Get these from Twilio Console: https://console.twilio.com

### Port Already in Use
```
Error: Address already in use
```
Use a different port:
```bash
python -m uvicorn app.main:app --reload --port 8001
```

## 9. Next Steps

1. Set up MongoDB Atlas for cloud database
2. Get Twilio credentials from console
3. Configure webhooks in Twilio
4. Test endpoints using Swagger UI
5. Implement authentication/authorization
6. Deploy to production (Heroku, AWS, etc.)

## Notes

- The `.env` file is not committed to git (listed in `.gitignore`)
- All Twilio webhooks are handled automatically
- MongoDB stores users, calls, and recordings
- View interactive API docs at `/docs` or `/redoc`
