import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Form
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
    CallFeedbackRequest,
    CallFeedbackResponse,
    CallStatus,
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
        db.ensure_track1_indexes()
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
async def create_outbound_call(request: OutboundCallRequest):
    """Create an outbound call with retry tracking"""
    try:
        logger.info(f"Creating outbound call to {request.to}")
        
        # Generate unique call_id
        call_id = str(uuid.uuid4())
        
        # Create Twilio call
        twilio_response = twilio_client.make_outbound_call(
            to_number=request.to,
            call_id=call_id,
            script=request.script,
            recording_enabled=request.recording_enabled,
        )
        
        call_sid = twilio_response["call_sid"]
        
        # Create call document with retry tracking
        call_doc = {
            "call_id": call_id,
            "user_id": request.user_external_id,
            "user_external_id": request.user_external_id,
            "to_number": request.to,
            "from_number": twilio_client.from_number,
            "call_sid": call_sid,
            "twilio_sid": call_sid,
            "status": twilio_response.get("status", "initiated"),
            "script": request.script,
            "recording_enabled": request.recording_enabled,
            "started_at": datetime.utcnow(),
            
            # RETRY TRACKING FIELDS
            "attempt_count": 1,
            "max_attempts": 3,
            "should_retry": False,
            "next_retry_at": None,
            "attempts": [{
                "attempt_number": 1,
                "twilio_sid": call_sid,
                "status": "initiated",
                "timestamp": datetime.utcnow(),
                "error_message": None
            }],
            
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert directly into MongoDB
        result = db.db.calls.insert_one(call_doc)
        
        logger.info(f"Call created successfully: {call_sid}")
        
        return OutboundCallResponse(
            call_id=call_id,
            user_id=request.user_external_id,
            to_number=request.to,
            status=CallStatus.INITIATED,
            created_at=datetime.utcnow(),
            twilio_sid=call_sid,
        )
        
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


@app.get("/calls/{call_sid}/debug")
async def get_call_debug(call_sid: str):
    """Debug endpoint to check call retry status"""
    try:
        # Find call by call_sid
        call = db.db.calls.find_one({"call_sid": call_sid})
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        return {
            "call_id": call.get("call_id"),
            "call_sid": call.get("call_sid"),
            "twilio_sid": call.get("twilio_sid"),
            "user_id": call.get("user_external_id"),
            "to": call.get("to_number"),
            "status": call.get("status"),
            "attempt_count": call.get("attempt_count", 1),
            "max_attempts": call.get("max_attempts", 3),
            "should_retry": call.get("should_retry", False),
            "next_retry_at": call.get("next_retry_at"),
            "attempts": call.get("attempts", []),
            "created_at": call.get("created_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get call debug info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Call Feedback Endpoints
# ============================================================================


@app.patch("/calls/{call_sid}/feedback", response_model=CallFeedbackResponse)
async def submit_call_feedback(call_sid: str, feedback: CallFeedbackRequest):
    """Submit feedback for a call"""
    try:
        # Validate call_sid format
        if not call_sid or not isinstance(call_sid, str) or len(call_sid.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid call_sid: must be a non-empty string"
            )

        # Verify call exists
        logger.info(f"Attempting to submit feedback for call: {call_sid}")
        call = db.get_call_by_twilio_sid(call_sid)
        if not call:
            logger.warning(f"Call not found: {call_sid}")
            raise HTTPException(status_code=404, detail=f"Call not found: {call_sid}")

        # Validate feedback data
        feedback_data = feedback.dict()

        # Additional validation for scores
        scores = {
            "call_quality": feedback_data.get("call_quality"),
            "agent_helpfulness": feedback_data.get("agent_helpfulness"),
            "resolution": feedback_data.get("resolution"),
            "call_ease": feedback_data.get("call_ease"),
            "overall_satisfaction": feedback_data.get("overall_satisfaction"),
        }

        for field_name, score in scores.items():
            if score is None or not isinstance(score, int) or score < 1 or score > 5:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {field_name}: must be an integer between 1 and 5"
                )

        # Validate notes if provided
        notes = feedback_data.get("notes")
        if notes is not None:
            if not isinstance(notes, str):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid notes: must be a string"
                )
            if len(notes) > 2000:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid notes: must not exceed 2000 characters"
                )

        # Save feedback to database
        logger.info(f"Saving feedback for call: {call_sid}")
        try:
            success = db.save_feedback(call_sid=call_sid, feedback_data=feedback_data)
        except Exception as db_error:
            logger.error(f"Database error while saving feedback: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail="Database error: failed to save feedback"
            )

        if not success:
            logger.error(f"Failed to save feedback for call: {call_sid}")
            raise HTTPException(
                status_code=500,
                detail="Failed to save feedback: call update returned no match"
            )

        # Retrieve and return saved feedback
        try:
            saved_feedback = db.get_call_feedback(call_sid)
        except Exception as db_error:
            logger.error(f"Database error while retrieving feedback: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail="Database error: feedback saved but could not be retrieved"
            )

        if not saved_feedback:
            logger.error(f"Feedback not found after save for call: {call_sid}")
            raise HTTPException(
                status_code=500,
                detail="Feedback saved but could not be retrieved"
            )

        logger.info(f"Feedback successfully submitted for call: {call_sid}")
        return CallFeedbackResponse(**saved_feedback)

    except HTTPException:
        raise
    except ValueError as val_error:
        logger.error(f"Validation error: {str(val_error)}")
        raise HTTPException(status_code=400, detail=f"Validation error: {str(val_error)}")
    except Exception as e:
        logger.error(f"Unexpected error while submitting feedback for call {call_sid}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error: unexpected error occurred"
        )


@app.get("/calls/{call_sid}/feedback", response_model=CallFeedbackResponse)
async def get_call_feedback(call_sid: str):
    """Get feedback for a specific call"""
    try:
        # Validate call_sid format
        if not call_sid or not isinstance(call_sid, str) or len(call_sid.strip()) == 0:
            logger.warning("Invalid call_sid provided for feedback retrieval")
            raise HTTPException(
                status_code=400,
                detail="Invalid call_sid: must be a non-empty string"
            )

        # Verify call exists
        logger.info(f"Attempting to retrieve feedback for call: {call_sid}")
        try:
            call = db.get_call_by_twilio_sid(call_sid)
        except Exception as db_error:
            logger.error(f"Database error while looking up call: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail="Database error: failed to look up call"
            )

        if not call:
            logger.warning(f"Call not found: {call_sid}")
            raise HTTPException(status_code=404, detail=f"Call not found: {call_sid}")

        # Get feedback
        try:
            feedback = db.get_call_feedback(call_sid)
        except Exception as db_error:
            logger.error(f"Database error while retrieving feedback: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail="Database error: failed to retrieve feedback"
            )

        if not feedback:
            logger.info(f"No feedback found for call: {call_sid}")
            raise HTTPException(
                status_code=404,
                detail=f"No feedback found for call: {call_sid}"
            )

        logger.info(f"Feedback successfully retrieved for call: {call_sid}")
        return CallFeedbackResponse(**feedback)

    except HTTPException:
        raise
    except ValueError as val_error:
        logger.error(f"Validation error: {str(val_error)}")
        raise HTTPException(status_code=400, detail=f"Validation error: {str(val_error)}")
    except Exception as e:
        logger.error(f"Unexpected error while retrieving feedback for call {call_sid}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error: unexpected error occurred"
        )


# ============================================================================
# Twilio Webhook Endpoints
# ============================================================================


@app.post("/twilio/voice")
async def handle_voice_callback(
    call_id: str = Query(...),
    recording: bool = Query(False),
):
    """Handle incoming voice requests from Twilio - Returns TwiML"""
    try:
        # Get call details from database
        call = None
        if call_id:
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
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred</Say></Response>',
            media_type="application/xml",
        )


@app.post("/twilio/status")
async def twilio_status_callback(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
):
    """Handle Twilio status callbacks with retry logic"""
    try:
        logger.info(f"Status callback: {CallSid} -> {CallStatus}")
        
        # Find the call by call_sid
        call = db.db.calls.find_one({"call_sid": CallSid})
        
        if not call:
            logger.warning(f"Call not found: {CallSid}")
            return {"status": "ok"}
        
        # Update the current attempt status in the attempts array
        attempts = call.get("attempts", [])
        for attempt in attempts:
            if attempt.get("twilio_sid") == CallSid:
                attempt["status"] = CallStatus
                if CallDuration:
                    attempt["duration"] = int(CallDuration)
                break
        
        # Prepare update data
        update_data = {
            "status": CallStatus,
            "attempts": attempts,
            "updated_at": datetime.utcnow()
        }
        
        # Add duration if provided
        if CallDuration:
            update_data["duration_sec"] = int(CallDuration)
        
        # RETRY LOGIC
        retry_statuses = ["busy", "no-answer", "failed"]
        attempt_count = call.get("attempt_count", 1)
        max_attempts = call.get("max_attempts", 3)
        can_retry = attempt_count < max_attempts
        
        if CallStatus in retry_statuses and can_retry:
            # Schedule retry with exponential backoff
            retry_delays = [2, 5, 10]  # minutes
            delay_index = attempt_count - 1
            delay_minutes = retry_delays[delay_index] if delay_index < len(retry_delays) else 10
            
            next_retry = datetime.utcnow() + timedelta(minutes=delay_minutes)
            
            update_data["should_retry"] = True
            update_data["next_retry_at"] = next_retry
            
            logger.info(f"Scheduling retry for {CallSid} in {delay_minutes} minutes (attempt {attempt_count + 1}/{max_attempts})")
        else:
            # No more retries
            update_data["should_retry"] = False
            update_data["next_retry_at"] = None
            
            if CallStatus == "completed":
                logger.info(f"Call {CallSid} completed successfully on attempt {attempt_count}")
            elif not can_retry:
                logger.info(f"Call {CallSid} reached max attempts ({max_attempts})")
        
        # Update call in database using call_sid
        db.db.calls.update_one(
            {"call_sid": CallSid},
            {"$set": update_data}
        )
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error in status callback: {str(e)}")
        return {"status": "ok"}


@app.post("/twilio/recording")
async def handle_recording_callback(
    RecordingSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingStatus: str = Form(...),
    CallSid: str = Form(...),
    AccountSid: str = Form(None),
    ApiVersion: str = Form(None),
    TranscriptionText: Optional[str] = Form(None),
):
    """Handle recording completion webhooks from Twilio"""
    try:
        logger.info(f"Received recording update: {RecordingSid} -> {RecordingStatus}")

        # Get call from database
        call = db.get_call_by_twilio_sid(CallSid)
        if not call:
            logger.warning(f"Call {CallSid} not found for recording {RecordingSid}")
            return {"status": "ok"}

        # Create or update recording record
        existing_recording = db.db.recordings.find_one({"twilio_sid": RecordingSid})

        recording_data = {
            "call_id": call.get("call_id"),
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
            db.update_call(call.get("call_id"), {"recording_url": RecordingUrl})

        # Save recording info
        db.save_recording(
            call_sid=CallSid,
            recording_url=RecordingUrl,
            transcription_text=TranscriptionText,
        )

        logger.info(f"Recording {RecordingSid} processed successfully")
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Failed to handle recording callback: {str(e)}")
        return {"status": "ok"}


# ============================================================================
# Background Retry Job
# ============================================================================

from apscheduler.schedulers.background import BackgroundScheduler

def process_retries():
    """Background job to process retry calls"""
    import asyncio
    asyncio.run(async_process_retries())


async def async_process_retries():
    """Async function to process retries"""
    try:
        # Find calls that need retry
        calls_cursor = db.db.calls.find({
            "should_retry": True,
            "next_retry_at": {"$lte": datetime.utcnow()},
            "attempt_count": {"$lt": 3}
        })
        
        calls = list(calls_cursor)
        
        if len(calls) > 0:
            logger.info(f"Processing {len(calls)} calls for retry")
        
        for call in calls:
            try:
                call_id = call.get("call_id")
                
                # Make new Twilio call
                new_call_response = twilio_client.make_outbound_call(
                    to_number=call["to_number"],
                    call_id=call_id,
                    script=call.get("script"),
                    recording_enabled=call.get("recording_enabled", True)
                )
                
                new_call_sid = new_call_response["call_sid"]
                
                # Update MongoDB
                new_attempt_number = call["attempt_count"] + 1
                
                db.db.calls.update_one(
                    {"_id": call["_id"]},
                    {
                        "$set": {
                            "attempt_count": new_attempt_number,
                            "should_retry": False,
                            "next_retry_at": None,
                            "updated_at": datetime.utcnow()
                        },
                        "$push": {
                            "attempts": {
                                "attempt_number": new_attempt_number,
                                "twilio_sid": new_call_sid,
                                "status": "initiated",
                                "timestamp": datetime.utcnow(),
                                "error_message": None
                            }
                        }
                    }
                )
                
                logger.info(f"✓ Retried call {call['call_sid']}, attempt {new_attempt_number}/3")
                
            except Exception as e:
                logger.error(f"✗ Error retrying call {call.get('call_sid')}: {str(e)}")
    
    except Exception as e:
        logger.error(f"✗ Error in retry job: {str(e)}")


# Start retry scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(process_retries, 'interval', minutes=1)
scheduler.start()

logger.info("✓ Retry scheduler started (runs every 1 minute)")


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
