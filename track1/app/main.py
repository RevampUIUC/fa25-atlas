import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uuid

from app.models import (
    User,
    UserCreate,
    OutboundCallRequest,
    OutboundCallResponse,
    TwilioWebhookRequest,
    RecordingWebhookRequest,
    HealthResponse,
    ErrorResponse,
    CallListResponse,
)
from app.dao import MongoDatabase
from app.twilio_client import TwilioClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Atlas - Twilio Call Management",
    description="API for managing outbound calls and recordings with Twilio",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
db: Optional[MongoDatabase] = None
twilio_client: Optional[TwilioClient] = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and Twilio client on startup"""
    global db, twilio_client

    try:
        db = MongoDatabase(
            connection_string=os.getenv("MONGO_URI"),
            database_name=os.getenv("MONGO_DB", "atlas"),
        )
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

    try:
        twilio_client = TwilioClient(
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            from_number=os.getenv("TWILIO_FROM_NUMBER"),
        )
        logger.info("Twilio client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global db

    if db:
        db.close()
        logger.info("Database connection closed")


# ============================================================================
# Health Check Endpoint
# ============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db.client.admin.command("ping")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"

    try:
        # Verify Twilio credentials
        account = twilio_client.client.api.accounts(
            twilio_client.account_sid
        ).fetch()
        twilio_status = "healthy"
    except Exception as e:
        logger.error(f"Twilio health check failed: {str(e)}")
        twilio_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" and twilio_status == "healthy" else "degraded",
        version="1.0.0",
        database=db_status,
        twilio=twilio_status,
    )


# ============================================================================
# User Endpoints
# ============================================================================


@app.get("/users", response_model=CallListResponse)
async def list_users(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    """List all users with pagination"""
    try:
        result = db.list_users(page=page, page_size=page_size)
        return CallListResponse(**result)
    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    """Get user by ID"""
    try:
        user = db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return User(**user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/users", response_model=User)
async def create_user(user: UserCreate):
    """Create a new user"""
    try:
        # Check if user with email already exists
        existing_user = db.get_user_by_email(user.email)
        if existing_user:
            raise HTTPException(status_code=409, detail="User with this email already exists")

        user_data = user.dict()
        user_id = db.create_user(user_data)

        created_user = db.get_user(user_id)
        return User(**created_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Call Endpoints
# ============================================================================


@app.post("/calls/outbound", response_model=OutboundCallResponse)
async def create_outbound_call(call_request: OutboundCallRequest):
    """Initiate an outbound call"""
    try:
        # Verify user exists
        user = db.get_user(call_request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Generate unique call ID
        call_id = str(uuid.uuid4())

        # Initiate Twilio call
        twilio_response = twilio_client.make_outbound_call(
            to_number=call_request.to_number,
            call_id=call_id,
            script=call_request.script,
            recording_enabled=call_request.recording_enabled,
        )

        # Store call record in database
        call_data = {
            "call_id": call_id,
            "user_id": call_request.user_id,
            "to_number": call_request.to_number,
            "from_number": twilio_client.from_number,
            "status": "initiated",
            "script": call_request.script,
            "recording_enabled": call_request.recording_enabled,
            "twilio_sid": twilio_response["call_sid"],
        }

        db_call_id = db.create_call(call_data)
        call_record = db.get_call(db_call_id)

        return OutboundCallResponse(**call_record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create outbound call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}/calls", response_model=CallListResponse)
async def list_user_calls(
    user_id: str, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)
):
    """List all calls for a specific user"""
    try:
        # Verify user exists
        user = db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        result = db.list_user_calls(user_id=user_id, page=page, page_size=page_size)
        return CallListResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list user calls: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Twilio Webhook Endpoints
# ============================================================================


@app.post("/twilio/voice")
async def handle_voice_callback(
    call_id: str = Query(...),
    recording: bool = Query(False),
):
    """
    Handle incoming voice requests from Twilio
    Returns TwiML for call handling
    """
    try:
        # Get call details from database
        call = None
        if call_id:
            # Search by call_id field
            call_record = db.db.calls.find_one({"call_id": call_id})
            if call_record:
                call = call_record

        # Generate TwiML response
        script = call.get("script") if call else None
        twiml = twilio_client.generate_twiml_response(
            script=script, record_call=recording
        )

        return Response(content=twiml, media_type="application/xml")
    except Exception as e:
        logger.error(f"Failed to handle voice callback: {str(e)}")
        # Return basic TwiML on error
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred</Say></Response>',
            media_type="application/xml",
        )


@app.post("/twilio/status")
async def handle_status_callback(
    CallSid: str,
    CallStatus: str,
    To: str,
    From: str,
    Direction: str = None,
    ApiVersion: str = None,
    AccountSid: str = None,
    Timestamp: str = None,
):
    """
    Handle call status updates from Twilio
    This webhook is called when call status changes
    """
    try:
        logger.info(f"Received status update: CallSid={CallSid}, Status={CallStatus}")

        # Update call status in database
        call_status_map = {
            "queued": "initiated",
            "ringing": "ringing",
            "in-progress": "in-progress",
            "completed": "completed",
            "failed": "failed",
            "busy": "busy",
            "no-answer": "no-answer",
        }

        status = call_status_map.get(CallStatus, CallStatus)

        update_data = {
            "status": status,
            "twilio_status": CallStatus,
            "to_number": To,
            "from_number": From,
        }

        if Direction:
            update_data["direction"] = Direction

        db.update_call_by_twilio_sid(CallSid, update_data)

        logger.info(f"Call {CallSid} status updated to {status}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to handle status callback: {str(e)}")
        return {"status": "ok"}  # Always return OK to prevent Twilio retries


@app.post("/twilio/recording")
async def handle_recording_callback(
    RecordingSid: str,
    RecordingUrl: str,
    RecordingStatus: str,
    CallSid: str,
    AccountSid: str = None,
    ApiVersion: str = None,
):
    """
    Handle recording completion webhooks from Twilio
    """
    try:
        logger.info(
            f"Received recording update: RecordingSid={RecordingSid}, Status={RecordingStatus}"
        )

        # Get call from database
        call = db.get_call_by_twilio_sid(CallSid)
        if not call:
            logger.warning(f"Call {CallSid} not found for recording {RecordingSid}")
            return {"status": "ok"}

        # Create or update recording record
        existing_recording = db.db.recordings.find_one(
            {"twilio_sid": RecordingSid}
        )

        recording_data = {
            "call_id": call.get("id"),
            "twilio_sid": RecordingSid,
            "recording_url": RecordingUrl,
            "recording_status": RecordingStatus,
            "status": "completed" if RecordingStatus == "completed" else "failed",
        }

        if existing_recording:
            db.update_recording(str(existing_recording["_id"]), recording_data)
        else:
            db.create_recording(recording_data)

        # Update call with recording URL
        if RecordingStatus == "completed":
            db.update_call(call.get("id"), {"recording_url": RecordingUrl})

        logger.info(f"Recording {RecordingSid} processed successfully")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to handle recording callback: {str(e)}")
        return {"status": "ok"}  # Always return OK to prevent Twilio retries


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return {
        "error": f"HTTP {exc.status_code}",
        "message": exc.detail,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Custom general exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Atlas - Twilio Call Management API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENVIRONMENT", "development") == "development",
    )
