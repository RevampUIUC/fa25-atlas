from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


class CallStatus(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no-answer"
    BUSY = "busy"


class RecordingStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., min_length=10, max_length=15)


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OutboundCallRequest(BaseModel):
    to: str = Field(..., min_length=10, max_length=15, description="Destination phone number")
    user_external_id: str = Field(..., min_length=1, description="External user identifier")
    script: Optional[str] = Field(None, max_length=5000)
    recording_enabled: bool = Field(default=True)


class OutboundCallResponse(BaseModel):
    call_id: str
    user_id: str
    to_number: str
    status: CallStatus
    created_at: datetime
    twilio_sid: Optional[str] = None

    class Config:
        from_attributes = True


class CallStatusUpdate(BaseModel):
    call_id: str
    status: CallStatus
    duration: Optional[int] = None
    recording_url: Optional[str] = None


class TwilioWebhookRequest(BaseModel):
    CallSid: str
    CallStatus: str
    To: str
    From: str
    Direction: str
    ApiVersion: str
    AccountSid: str
    Timestamp: str


class RecordingWebhookRequest(BaseModel):
    RecordingSid: str
    RecordingUrl: str
    RecordingStatus: str
    CallSid: str
    AccountSid: str
    ApiVersion: str


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    twilio: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List


class CallListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[OutboundCallResponse]


class CallFeedbackRequest(BaseModel):
    """Call feedback with five scoring dimensions"""
    call_quality: int = Field(..., ge=1, le=5, description="Call audio quality (1-5)")
    agent_helpfulness: int = Field(..., ge=1, le=5, description="Agent helpfulness (1-5)")
    resolution: int = Field(..., ge=1, le=5, description="Issue resolution (1-5)")
    call_ease: int = Field(..., ge=1, le=5, description="Ease of call experience (1-5)")
    overall_satisfaction: int = Field(..., ge=1, le=5, description="Overall satisfaction (1-5)")
    notes: Optional[str] = Field(None, max_length=2000, description="Optional feedback notes")


class CallFeedbackResponse(BaseModel):
    """Call feedback response"""
    call_sid: str
    call_quality: int
    agent_helpfulness: int
    resolution: int
    call_ease: int
    overall_satisfaction: int
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CallRetryRequest(BaseModel):
    """Request to retry failed calls"""
    call_sid: Optional[str] = Field(None, description="Specific call SID to retry (optional)")
    user_external_id: Optional[str] = Field(None, description="Retry all failed calls for this user (optional)")
    max_retry_attempts: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts (1-10)")
    retry_statuses: List[str] = Field(
        default=["failed", "no-answer", "busy"],
        description="Call statuses to retry"
    )


class CallRetryResult(BaseModel):
    """Result of a single call retry"""
    original_call_sid: str
    new_call_sid: Optional[str]
    to_number: str
    status: str
    message: str


class CallRetryResponse(BaseModel):
    """Response from retry endpoint"""
    total_attempted: int
    successful_retries: int
    failed_retries: int
    results: List[CallRetryResult]
