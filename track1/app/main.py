import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request, WebSocket
from fastapi.responses import Response, JSONResponse
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
    CallRetryRequest,
    CallRetryResult,
    CallRetryResponse,
)
from app.dao import MongoDatabase
from app.twilio_client import (
    TwilioClient,
    TwilioError,
    TwilioValidationError,
    TwilioRateLimitError,
    TwilioAuthenticationError,
    TwilioPermissionError,
    TwilioResourceError,
)
from app.transcript_schema import initialize_transcript_collection
from app.voicemail_detector import VoicemailDetector
from app.transcript_utils import TranscriptQuery

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
media_stream_handler = None
voicemail_detector: Optional[VoicemailDetector] = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and Twilio client on startup"""
    global db, twilio_client, media_stream_handler, voicemail_detector

    try:
        db = MongoDatabase(
            connection_string=os.getenv("MONGO_URI"),
            database_name=os.getenv("MONGO_DB", "atlas"),
        )
        db.ensure_track1_indexes()
        logger.info("Database initialized successfully")

        # Initialize transcript collection with schema validation and indexes
        try:
            initialize_transcript_collection(db.db)
            logger.info("Transcript collection initialized with schema validation and indexes")
        except Exception as transcript_error:
            logger.warning(f"Failed to initialize transcript collection: {str(transcript_error)}")
            # Don't fail startup if transcript initialization fails

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

    try:
        from app.media_stream_handler import TwilioMediaStreamHandler
        media_stream_handler = TwilioMediaStreamHandler(db=db)
        logger.info("Media stream handler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize media stream handler: {str(e)}")
        # Don't raise - this is optional functionality
        logger.warning("Deepgram transcription will not be available")

    # Initialize voicemail detector
    try:
        voicemail_detector = VoicemailDetector(
            amd_confidence_threshold=float(os.getenv("VOICEMAIL_AMD_THRESHOLD", "0.85")),
            keyword_confidence_threshold=float(os.getenv("VOICEMAIL_KEYWORD_THRESHOLD", "0.75")),
            min_signals_required=int(os.getenv("VOICEMAIL_MIN_SIGNALS", "1")),
            enable_aggressive_detection=os.getenv("VOICEMAIL_AGGRESSIVE", "false").lower() == "true"
        )
        logger.info("Voicemail detector initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize voicemail detector: {str(e)}")
        # Don't raise - this is optional functionality
        logger.warning("Voicemail detection will not be available")


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
    """Initiate an outbound call

    Args:
        call_request: Request containing:
            - to: Destination phone number
            - user_external_id: External user identifier
            - script: Optional script/message for the call
            - recording_enabled: Whether to record the call (default: True)

    Returns:
        OutboundCallResponse with call_sid and other call details

    Raises:
        400: Invalid phone number or request parameters
        429: Rate limit exceeded
        401: Authentication failed
        403: Permission denied
        500: Internal server error
    """
    try:
        # Generate unique call ID
        call_id = str(uuid.uuid4())

        # Initiate Twilio call
        twilio_response = twilio_client.make_outbound_call(
            to_number=call_request.to,
            call_id=call_id,
            script=call_request.script,
            recording_enabled=call_request.recording_enabled,
        )

        # Store call record in database
        call_data = {
            "call_id": call_id,
            "user_external_id": call_request.user_external_id,
            "to_number": call_request.to,
            "from_number": twilio_client.from_number,
            "status": "initiated",
            "script": call_request.script,
            "recording_enabled": call_request.recording_enabled,
            "twilio_sid": twilio_response["call_sid"],
        }

        db_call_id = db.create_call(call_data)
        call_record = db.get_call(db_call_id)
        retry_limit = int(os.getenv("RETRY_LIMIT", 3))
        retry_delay = int(os.getenv("RETRY_DELAY", 10))
        db.init_retry_plan(twilio_response["call_sid"], retry_limit, retry_delay)

        return OutboundCallResponse(**call_record)

    except TwilioValidationError as e:
        logger.error(f"Validation error creating outbound call: {e.message} (Twilio code: {e.twilio_code})")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid request parameters",
                "message": e.message,
                "twilio_code": e.twilio_code
            }
        )
    except TwilioRateLimitError as e:
        logger.error(f"Rate limit error creating outbound call: {e.message} (Twilio code: {e.twilio_code})")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": e.message,
                "twilio_code": e.twilio_code,
                "retry_after": "Please try again later"
            }
        )
    except TwilioAuthenticationError as e:
        logger.error(f"Authentication error creating outbound call: {e.message} (Twilio code: {e.twilio_code})")
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authentication failed",
                "message": "Twilio authentication failed. Please check server configuration.",
                "twilio_code": e.twilio_code
            }
        )
    except TwilioPermissionError as e:
        logger.error(f"Permission error creating outbound call: {e.message} (Twilio code: {e.twilio_code})")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Permission denied",
                "message": e.message,
                "twilio_code": e.twilio_code
            }
        )
    except TwilioError as e:
        logger.error(f"Twilio error creating outbound call: {e.message} (Twilio code: {e.twilio_code})")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": "Twilio service error",
                "message": e.message,
                "twilio_code": e.twilio_code
            }
        )
    except Exception as e:
        logger.error(f"Failed to create outbound call: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred while creating the call"
            }
        )


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
# Call Feedback Endpoints
# ============================================================================


@app.patch("/calls/{call_sid}/feedback", response_model=CallFeedbackResponse)
async def submit_call_feedback(call_sid: str, feedback: CallFeedbackRequest):
    """
    Submit feedback for a call

    Args:
        call_sid: Twilio Call SID
        feedback: Feedback request with five scoring fields and optional notes

    Returns:
        CallFeedbackResponse with submitted feedback

    Raises:
        404: Call not found
        400: Invalid feedback data
        500: Database or server error
    """
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
    """
    Get feedback for a specific call

    Args:
        call_sid: Twilio Call SID

    Returns:
        CallFeedbackResponse if feedback exists, 404 if not

    Raises:
        404: Call not found or no feedback for call
        500: Database or server error
    """
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


async def run_voicemail_detection(call_sid: str, answered_by: str, call_duration: Optional[int] = None):
    """
    Background task to run voicemail detection on a completed call

    Args:
        call_sid: The Twilio Call SID
        answered_by: Twilio's answeredBy parameter
        call_duration: Call duration in seconds
    """
    try:
        if not voicemail_detector:
            logger.warning(f"Voicemail detector not initialized, skipping detection for {call_sid}")
            return

        logger.info(f"Running voicemail detection for call: {call_sid}")

        # Get call details
        call = db.get_call_by_twilio_sid(call_sid)
        if not call:
            logger.error(f"Call not found for voicemail detection: {call_sid}")
            return

        # Get transcripts from database
        transcripts = None
        try:
            transcripts = list(TranscriptQuery.by_call(
                db.db,
                call_sid=call_sid,
                final_only=True  # Only use final transcripts
            ))
            logger.info(f"Found {len(transcripts) if transcripts else 0} transcripts for call {call_sid}")
        except Exception as transcript_error:
            logger.warning(f"Failed to fetch transcripts for {call_sid}: {str(transcript_error)}")
            transcripts = None

        # Run detection
        result = voicemail_detector.analyze_call(
            call_sid=call_sid,
            answered_by=answered_by,
            transcripts=transcripts,
            call_duration=call_duration,
            metadata=call.get("metadata", {})
        )

        # Save detection result to database
        voicemail_data = {
            "is_voicemail": result.is_voicemail,
            "voicemail_confidence": result.confidence,
            "voicemail_detection_method": result.detection_method,
            "voicemail_signals": [
                {
                    "type": signal.signal_type,
                    "confidence": signal.confidence,
                    "detected_at": signal.detected_at.isoformat(),
                    "details": signal.details
                }
                for signal in result.signals
            ],
            "voicemail_metadata": result.metadata
        }

        db.update_call_by_twilio_sid(call_sid, voicemail_data)

        logger.info(
            f"Voicemail detection completed for {call_sid}: "
            f"is_voicemail={result.is_voicemail}, "
            f"confidence={result.confidence:.2f}, "
            f"method={result.detection_method}"
        )

    except Exception as e:
        logger.error(f"Failed to run voicemail detection for {call_sid}: {str(e)}")


async def retry_call_background(call_sid: str, max_attempts: int = 3):
    """
    Background task to retry a failed call

    Args:
        call_sid: The Twilio Call SID of the failed call
        max_attempts: Maximum number of retry attempts
    """
    try:
        logger.info(f"Background retry task started for call: {call_sid}")

        # Get the original call details
        call = db.get_call_by_twilio_sid(call_sid)
        if not call:
            logger.error(f"Cannot retry - call not found: {call_sid}")
            return

        # Check retry count
        retry_count = call.get("retry_count", 0)
        if retry_count >= max_attempts:
            logger.info(f"Call {call_sid} has reached max retry attempts ({max_attempts})")
            return

        # Extract call details
        to_number = call.get("to_number")
        user_external_id = call.get("user_external_id")
        script = call.get("script")
        recording_enabled = call.get("recording_enabled", True)

        if not to_number:
            logger.error(f"Cannot retry - no destination number for call: {call_sid}")
            return

        # Generate new call ID
        new_call_id = str(uuid.uuid4())

        logger.info(f"Retrying call {call_sid} to {to_number} (attempt {retry_count + 1}/{max_attempts})")

        # Initiate retry call
        twilio_response = twilio_client.make_outbound_call(
            to_number=to_number,
            call_id=new_call_id,
            script=script,
            recording_enabled=recording_enabled,
        )

        # Store new call record
        new_call_data = {
            "call_id": new_call_id,
            "user_external_id": user_external_id,
            "to_number": to_number,
            "from_number": twilio_client.from_number,
            "status": "initiated",
            "script": script,
            "recording_enabled": recording_enabled,
            "twilio_sid": twilio_response["call_sid"],
            "is_retry": True,
            "retry_of_call_sid": call_sid,
            "retry_attempt": retry_count + 1,
        }

        db_call_id = db.create_call(new_call_data)

        # Update original call's retry count
        db.update_call_by_twilio_sid(
            call_sid,
            {"retry_count": retry_count + 1}
        )

        logger.info(f"Successfully retried call {call_sid} -> {twilio_response['call_sid']}")

    except Exception as e:
        logger.error(f"Failed to retry call {call_sid} in background: {str(e)}")


@app.post("/twilio/status")
async def handle_status_callback(
    background_tasks: BackgroundTasks,
    CallSid: str,
    CallStatus: str,
    To: str,
    From: str,
    Direction: str = None,
    ApiVersion: str = None,
    AccountSid: str = None,
    Timestamp: str = None,
    CallDuration: Optional[int] = None,
    AnsweredBy: str = None,  # AMD result: human, machine_start, machine_end_beep, etc.
):
    """
    Handle call status updates from Twilio
    This webhook is called when call status changes
    Automatically enqueues retry tasks for failed calls
    Captures answeredBy parameter for voicemail detection
    """
    try:
        logger.info(f"Received status update: CallSid={CallSid}, Status={CallStatus}, AnsweredBy={AnsweredBy}")

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

        # Capture answeredBy parameter for voicemail detection
        if AnsweredBy:
            update_data["answered_by"] = AnsweredBy

        db.update_call_by_twilio_sid(CallSid, update_data)
        # NEW: also set duration/ended_at via Track-1 contract
        ended_at = (
            datetime.utcnow()
            if CallStatus in ("completed", "failed", "busy", "no-answer")
            else None
        )

        # Derive next attempt number from current count
        call_doc = db.get_call_by_twilio_sid(CallSid) or {}
        next_attempt_no = int(call_doc.get("attempt_count", 0)) + 1

        # Reason is the raw Twilio status (helpful for auditing)
        reason = CallStatus

        # Log attempt (for all terminal/non-terminal statuses)
        db.log_call_attempt(
            twilio_sid=CallSid,
            attempt_no=next_attempt_no,
            status=status,
            reason=reason,
        )

        # this won’t break anything; it upserts by call_sid if needed
        db.update_call_status(
            call_sid=CallSid,
            status=status,
            duration_sec=CallDuration,
            ended_at=ended_at,
            meta={"raw": {
                "To": To, "From": From, "Direction": Direction,
                "ApiVersion": ApiVersion, "AccountSid": AccountSid,
                "Timestamp": Timestamp, "CallStatus": CallStatus
            }},
        )

        logger.info(f"Call {CallSid} status updated to {status}")

        # Enqueue background retry task for failed calls
        retry_statuses = ["failed", "no-answer", "busy"]
        if status in retry_statuses:
            logger.info(f"Enqueuing background retry task for call {CallSid} with status {status}")
            background_tasks.add_task(retry_call_background, CallSid, 3)

        # Enqueue voicemail detection for completed calls
        if CallStatus == "completed" and AnsweredBy:
            logger.info(f"Enqueuing voicemail detection for call {CallSid}")
            background_tasks.add_task(run_voicemail_detection, CallSid, AnsweredBy, CallDuration)

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
    TranscriptionText: Optional[str] = None,
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

        db.save_recording(
            call_sid=CallSid,
            recording_url=RecordingUrl,
            transcription_text=TranscriptionText,
        )

        logger.info(f"Recording {RecordingSid} processed successfully")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to handle recording callback: {str(e)}")
        return {"status": "ok"}  # Always return OK to prevent Twilio retries


@app.websocket("/twilio/stream")
async def handle_media_stream(websocket: WebSocket):
    """
    Handle Twilio Media Streams WebSocket connection
    Receives real-time audio and sends to Deepgram for transcription

    This endpoint receives mulaw-encoded audio at 8kHz from Twilio
    and forwards it to Deepgram for real-time speech-to-text transcription
    """
    try:
        if media_stream_handler:
            await media_stream_handler.handle_connection(websocket)
        else:
            logger.error("Media stream handler not initialized")
            await websocket.close(code=1011, reason="Transcription service unavailable")
    except Exception as e:
        logger.error(f"Error in media stream endpoint: {str(e)}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


@app.post("/twilio/retry", response_model=CallRetryResponse)
async def retry_failed_calls(retry_request: CallRetryRequest):
    """
    Retry failed calls automatically

    This endpoint allows retrying calls that failed, weren't answered, or were busy.
    You can retry a specific call by call_sid, all failed calls for a user, or
    all calls matching the specified retry statuses.

    Args:
        retry_request: Request containing:
            - call_sid: Optional specific call SID to retry
            - user_external_id: Optional user external ID to retry all their failed calls
            - max_retry_attempts: Maximum number of retry attempts (default: 3)
            - retry_statuses: List of call statuses to retry (default: ["failed", "no-answer", "busy"])

    Returns:
        CallRetryResponse with summary and detailed results of retry attempts

    Raises:
        400: Invalid request parameters
        404: No calls found matching criteria
        500: Server error during retry
    """
    try:
        logger.info(f"Retry request received: {retry_request.dict()}")

        # Validate request - at least one of call_sid or user_external_id should be provided
        if not retry_request.call_sid and not retry_request.user_external_id:
            # If neither is provided, retry all calls with matching statuses
            logger.info(f"Retrying all calls with statuses: {retry_request.retry_statuses}")

        calls_to_retry = []

        # Case 1: Retry specific call by call_sid
        if retry_request.call_sid:
            call = db.get_call_by_twilio_sid(retry_request.call_sid)
            if not call:
                raise HTTPException(
                    status_code=404,
                    detail=f"Call not found: {retry_request.call_sid}"
                )

            # Check if call status is eligible for retry
            if call.get("status") not in retry_request.retry_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Call status '{call.get('status')}' is not eligible for retry. Eligible statuses: {retry_request.retry_statuses}"
                )

            # Check retry count
            retry_count = call.get("retry_count", 0)
            if retry_count >= retry_request.max_retry_attempts:
                raise HTTPException(
                    status_code=400,
                    detail=f"Call has already been retried {retry_count} times (max: {retry_request.max_retry_attempts})"
                )

            calls_to_retry.append(call)

        # Case 2: Retry all failed calls for a specific user
        elif retry_request.user_external_id:
            # Find user by external_id
            user = db.db.users.find_one({"external_id": retry_request.user_external_id})
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail=f"User not found: {retry_request.user_external_id}"
                )

            user_id = str(user["_id"])

            # Find all calls for this user with eligible statuses
            calls_cursor = db.db.calls.find({
                "user_id": user_id,
                "status": {"$in": retry_request.retry_statuses}
            })

            for call in calls_cursor:
                retry_count = call.get("retry_count", 0)
                if retry_count < retry_request.max_retry_attempts:
                    calls_to_retry.append(call)

        # Case 3: Retry all calls with matching statuses
        else:
            calls_cursor = db.db.calls.find({
                "status": {"$in": retry_request.retry_statuses}
            })

            for call in calls_cursor:
                retry_count = call.get("retry_count", 0)
                if retry_count < retry_request.max_retry_attempts:
                    calls_to_retry.append(call)

        if not calls_to_retry:
            raise HTTPException(
                status_code=404,
                detail="No eligible calls found for retry"
            )

        logger.info(f"Found {len(calls_to_retry)} calls eligible for retry")

        # Retry each call
        results = []
        successful_retries = 0
        failed_retries = 0

        for call in calls_to_retry:
            original_call_sid = call.get("twilio_sid") or call.get("call_sid")
            to_number = call.get("to_number")
            user_external_id = call.get("user_external_id")
            script = call.get("script")
            recording_enabled = call.get("recording_enabled", True)
            retry_count = call.get("retry_count", 0)

            try:
                # Generate new call ID
                new_call_id = str(uuid.uuid4())

                # Initiate retry call
                twilio_response = twilio_client.make_outbound_call(
                    to_number=to_number,
                    call_id=new_call_id,
                    script=script,
                    recording_enabled=recording_enabled,
                )

                # Store new call record
                new_call_data = {
                    "call_id": new_call_id,
                    "user_external_id": user_external_id,
                    "to_number": to_number,
                    "from_number": twilio_client.from_number,
                    "status": "initiated",
                    "script": script,
                    "recording_enabled": recording_enabled,
                    "twilio_sid": twilio_response["call_sid"],
                    "is_retry": True,
                    "retry_of_call_sid": original_call_sid,
                    "retry_attempt": retry_count + 1,
                }

                db_call_id = db.create_call(new_call_data)

                # Update original call's retry count
                db.update_call_by_twilio_sid(
                    original_call_sid,
                    {"retry_count": retry_count + 1}
                )

                successful_retries += 1
                results.append(CallRetryResult(
                    original_call_sid=original_call_sid,
                    new_call_sid=twilio_response["call_sid"],
                    to_number=to_number,
                    status="success",
                    message=f"Call retry initiated successfully (attempt {retry_count + 1})"
                ))

                logger.info(f"Successfully retried call {original_call_sid} -> {twilio_response['call_sid']}")

            except Exception as e:
                failed_retries += 1
                error_message = str(e)
                results.append(CallRetryResult(
                    original_call_sid=original_call_sid,
                    new_call_sid=None,
                    to_number=to_number,
                    status="failed",
                    message=f"Failed to retry call: {error_message}"
                ))

                logger.error(f"Failed to retry call {original_call_sid}: {error_message}")

        response = CallRetryResponse(
            total_attempted=len(calls_to_retry),
            successful_retries=successful_retries,
            failed_retries=failed_retries,
            results=results
        )

        logger.info(f"Retry operation completed: {successful_retries} successful, {failed_retries} failed")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during call retry: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry calls: {str(e)}"
        )


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(TwilioValidationError)
async def twilio_validation_error_handler(request: Request, exc: TwilioValidationError):
    """Handle Twilio validation errors (invalid phone numbers, etc.)"""
    logger.error(f"Twilio validation error: {exc.message} (code: {exc.twilio_code})")
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid request parameters",
            "message": exc.message,
            "twilio_code": exc.twilio_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.exception_handler(TwilioRateLimitError)
async def twilio_rate_limit_error_handler(request: Request, exc: TwilioRateLimitError):
    """Handle Twilio rate limit errors"""
    logger.error(f"Twilio rate limit error: {exc.message} (code: {exc.twilio_code})")
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": exc.message,
            "twilio_code": exc.twilio_code,
            "retry_after": "Please try again later",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.exception_handler(TwilioAuthenticationError)
async def twilio_auth_error_handler(request: Request, exc: TwilioAuthenticationError):
    """Handle Twilio authentication errors"""
    logger.error(f"Twilio authentication error: {exc.message} (code: {exc.twilio_code})")
    return JSONResponse(
        status_code=401,
        content={
            "error": "Authentication failed",
            "message": "Twilio service authentication failed. Please contact support.",
            "twilio_code": exc.twilio_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.exception_handler(TwilioPermissionError)
async def twilio_permission_error_handler(request: Request, exc: TwilioPermissionError):
    """Handle Twilio permission errors"""
    logger.error(f"Twilio permission error: {exc.message} (code: {exc.twilio_code})")
    return JSONResponse(
        status_code=403,
        content={
            "error": "Permission denied",
            "message": exc.message,
            "twilio_code": exc.twilio_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.exception_handler(TwilioResourceError)
async def twilio_resource_error_handler(request: Request, exc: TwilioResourceError):
    """Handle Twilio resource not found errors"""
    logger.error(f"Twilio resource error: {exc.message} (code: {exc.twilio_code})")
    return JSONResponse(
        status_code=404,
        content={
            "error": "Resource not found",
            "message": exc.message,
            "twilio_code": exc.twilio_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.exception_handler(TwilioError)
async def twilio_error_handler(request: Request, exc: TwilioError):
    """Handle general Twilio errors"""
    logger.error(f"Twilio error: {exc.message} (code: {exc.twilio_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Twilio service error",
            "message": exc.message,
            "twilio_code": exc.twilio_code,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


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
