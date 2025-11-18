import os
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TwilioError(Exception):
    """Base exception for Twilio-related errors"""
    def __init__(self, message: str, status_code: int = 500, twilio_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        self.twilio_code = twilio_code
        super().__init__(self.message)


class TwilioValidationError(TwilioError):
    """Exception for invalid phone numbers or validation errors"""
    def __init__(self, message: str, twilio_code: Optional[int] = None):
        super().__init__(message, status_code=400, twilio_code=twilio_code)


class TwilioRateLimitError(TwilioError):
    """Exception for rate limiting errors"""
    def __init__(self, message: str, twilio_code: Optional[int] = None):
        super().__init__(message, status_code=429, twilio_code=twilio_code)


class TwilioAuthenticationError(TwilioError):
    """Exception for authentication errors"""
    def __init__(self, message: str, twilio_code: Optional[int] = None):
        super().__init__(message, status_code=401, twilio_code=twilio_code)


class TwilioPermissionError(TwilioError):
    """Exception for permission/authorization errors"""
    def __init__(self, message: str, twilio_code: Optional[int] = None):
        super().__init__(message, status_code=403, twilio_code=twilio_code)


class TwilioResourceError(TwilioError):
    """Exception for resource not found or unavailable"""
    def __init__(self, message: str, twilio_code: Optional[int] = None):
        super().__init__(message, status_code=404, twilio_code=twilio_code)


class TwilioClient:
    """Wrapper for Twilio API interactions"""

    def __init__(
        self,
        account_sid: str = None,
        auth_token: str = None,
        from_number: str = None,
    ):
        """
        Initialize Twilio client

        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: Default Twilio phone number for outbound calls
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_FROM_NUMBER")
        self.base_url = os.getenv("BASE_URL")

        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError(
                "Missing required Twilio configuration: TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER"
            )

        self.client = Client(self.account_sid, self.auth_token)

    def _handle_twilio_exception(self, e: Exception) -> None:
        """
        Parse Twilio exceptions and raise appropriate custom exceptions

        Args:
            e: The exception from Twilio API

        Raises:
            TwilioValidationError: For validation errors (invalid numbers, etc.)
            TwilioRateLimitError: For rate limit errors
            TwilioAuthenticationError: For authentication errors
            TwilioPermissionError: For permission errors
            TwilioResourceError: For resource not found errors
            TwilioError: For other Twilio errors
        """
        if not isinstance(e, TwilioRestException):
            # Not a Twilio exception, raise generic error
            raise TwilioError(f"Unexpected error: {str(e)}", status_code=500)

        error_code = e.code
        error_msg = e.msg
        status = e.status

        # Map Twilio error codes to appropriate exceptions
        # https://www.twilio.com/docs/api/errors

        # Validation errors (400-level)
        validation_codes = [
            21211,  # Invalid 'To' Phone Number
            21217,  # Phone number not verified (trial account)
            21401,  # Invalid Phone Number
            21402,  # Invalid URL
            21421,  # PhoneNumber Requires a Local Address
            21422,  # Invalid StatusCallback URL
            21603,  # Cannot create Call without a valid phone number
            21604,  # Phone number is not a valid SMS-capable inbound phone number
            14101,  # Invalid 'To' Phone Number
            14102,  # Invalid 'From' Phone Number
        ]

        # Rate limit errors
        rate_limit_codes = [
            20003,  # Permission Denied / Rate limit
            20429,  # Too Many Requests
        ]

        # Authentication errors
        auth_codes = [
            20003,  # Authenticate (invalid credentials)
            20005,  # Account not active
        ]

        # Permission/Authorization errors
        permission_codes = [
            20403,  # Forbidden
            21218,  # Invalid ApplicationSid
        ]

        # Resource errors
        resource_codes = [
            20404,  # Resource not found
            21220,  # Invalid call SID
        ]

        if error_code in validation_codes:
            raise TwilioValidationError(
                f"Invalid phone number or request parameter: {error_msg}",
                twilio_code=error_code
            )
        elif error_code in rate_limit_codes or status == 429:
            raise TwilioRateLimitError(
                f"Rate limit exceeded: {error_msg}",
                twilio_code=error_code
            )
        elif error_code in auth_codes and status == 401:
            raise TwilioAuthenticationError(
                f"Authentication failed: {error_msg}",
                twilio_code=error_code
            )
        elif error_code in permission_codes or status == 403:
            raise TwilioPermissionError(
                f"Permission denied: {error_msg}",
                twilio_code=error_code
            )
        elif error_code in resource_codes or status == 404:
            raise TwilioResourceError(
                f"Resource not found: {error_msg}",
                twilio_code=error_code
            )
        else:
            # Generic Twilio error
            raise TwilioError(
                f"Twilio API error: {error_msg}",
                status_code=status if status else 500,
                twilio_code=error_code
            )

    def make_outbound_call(
        self,
        to_number: str,
        call_id: str,
        script: Optional[str] = None,
        recording_enabled: bool = True,
        machine_detection: bool = True,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call

        Args:
            to_number: Destination phone number
            call_id: Unique call identifier
            script: Optional TwiML script or URL
            recording_enabled: Whether to record the call
            machine_detection: Enable answering machine detection (AMD)

        Returns:
            Dict with call_sid and status

        Raises:
            TwilioValidationError: For invalid phone numbers or parameters
            TwilioRateLimitError: For rate limit exceeded
            TwilioAuthenticationError: For authentication issues
            TwilioError: For other Twilio errors
        """
        try:
            # Build the URL to fetch TwiML from our voice endpoint
            voice_url = f"{self.base_url}/twilio/voice?call_id={call_id}&streaming=true"

            # Add recording parameter if enabled
            if recording_enabled:
                voice_url += "&recording=true"

            # Configure call parameters
            call_params = {
                "to": to_number,
                "from_": self.from_number,
                "url": voice_url,
                "status_callback": f"{self.base_url}/twilio/status",
                "status_callback_event": ["initiated", "ringing", "answered", "completed"],
                "status_callback_method": "POST",
            }

            # Enable Answering Machine Detection (AMD) if requested
            if machine_detection:
                call_params.update({
                    "machine_detection": "DetectMessageEnd",  # or "Enable" for faster detection
                    "machine_detection_timeout": 30,  # seconds to wait for detection
                    "machine_detection_speech_threshold": 2400,  # ms of speech to detect machine
                    "machine_detection_speech_end_threshold": 1200,  # ms of silence after speech
                    "machine_detection_silence_timeout": 5000,  # ms of silence before giving up
                })

            call = self.client.calls.create(**call_params)

            logger.info(f"Outbound call initiated: {call.sid} to {to_number} (AMD: {machine_detection})")
            return {"call_sid": call.sid, "status": "initiated"}

        except (TwilioError, TwilioValidationError, TwilioRateLimitError,
                TwilioAuthenticationError, TwilioPermissionError, TwilioResourceError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to initiate outbound call: {str(e)}")
            self._handle_twilio_exception(e)

    def get_call_details(self, call_sid: str) -> Dict[str, Any]:
        """
        Get details of a specific call

        Args:
            call_sid: Twilio Call SID

        Returns:
            Dict with call details

        Raises:
            TwilioResourceError: If call SID not found
            TwilioError: For other Twilio errors
        """
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "call_sid": call.sid,
                "status": call.status,
                "direction": call.direction,
                "from": call.from_,
                "to": call.to,
                "duration": call.duration,
                "start_time": call.start_time,
                "end_time": call.end_time,
            }
        except (TwilioError, TwilioValidationError, TwilioRateLimitError,
                TwilioAuthenticationError, TwilioPermissionError, TwilioResourceError):
            raise
        except Exception as e:
            logger.error(f"Failed to get call details for {call_sid}: {str(e)}")
            self._handle_twilio_exception(e)

    def generate_twiml_response(
        self,
        script: Optional[str] = None,
        record_call: bool = True,
        enable_streaming: bool = True,
        call_id: str = None,
    ) -> str:
        """
        Generate TwiML response for voice calls with media streaming (Week 3)

        Args:
            script: Text to speak (speech synthesis)
            record_call: Whether to record the call
            enable_streaming: Enable real-time media streaming for transcription
            call_id: Call ID for streaming identification

        Returns:
            TwiML response as string
        """
        response = VoiceResponse()

        # Week 3: Start media streaming for real-time transcription
        if enable_streaming and call_id:
            # Determine WebSocket URL based on base_url protocol
            ws_url = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://')
            stream_url = f"{ws_url}/twilio/media-stream"
            
            # Connect to WebSocket for real-time audio streaming
            connect = Connect()
            stream = Stream(url=stream_url)
            stream.parameter(name="call_id", value=call_id)
            connect.append(stream)
            response.append(connect)
            
            logger.info(f"Media streaming enabled for call {call_id} at {stream_url}")

        # Client-approved consent message
        consent_message = (
            "This call may be recorded for quality assurance and training purposes. "
            "By remaining on the line, you consent to this recording. "
            "If you do not consent, please hang up now."
        )

        # Say greeting with consent disclosure
        response.say(consent_message, voice="alice")

        # Add custom script if provided
        if script:
            response.say(script, voice="alice")
        else:
            response.say(
                "Thank you for answering. Please leave a message after the beep.",
                voice="alice",
            )

        # Record the call with transcription callback
        if record_call:
            response.record(
                max_speech_time=3600,
                speech_timeout=5,
                trim="trim-silence",
                transcribe="true",
                transcribe_callback=f"{self.base_url}/twilio/recording",
                recording_status_callback=f"{self.base_url}/twilio/recording",
                recording_status_callback_method="POST",
            )

        response.hangup()

        return str(response)

    def get_recording_url(self, recording_sid: str) -> str:
        """
        Get the URL of a recording

        Args:
            recording_sid: Twilio Recording SID

        Returns:
            Recording URL

        Raises:
            TwilioResourceError: If recording not found
            TwilioError: For other Twilio errors
        """
        try:
            recording = self.client.recordings(recording_sid).fetch()
            # Get the transcription if available
            transcriptions = self.client.transcriptions.stream(
                recording_sid=recording_sid, limit=1
            )
            transcription_text = None
            for transcription in transcriptions:
                transcription_text = transcription.transcription_text

            return {
                "recording_url": recording.uri,
                "recording_sid": recording.sid,
                "duration": recording.duration,
                "transcription": transcription_text,
            }
        except (TwilioError, TwilioValidationError, TwilioRateLimitError,
                TwilioAuthenticationError, TwilioPermissionError, TwilioResourceError):
            raise
        except Exception as e:
            logger.error(f"Failed to get recording URL for {recording_sid}: {str(e)}")
            self._handle_twilio_exception(e)

    def hangup_call(self, call_sid: str) -> bool:
        """
        Terminate an active call

        Args:
            call_sid: Twilio Call SID

        Returns:
            True if successful

        Raises:
            TwilioResourceError: If call not found
            TwilioError: For other Twilio errors
        """
        try:
            call = self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call terminated: {call.sid}")
            return True
        except (TwilioError, TwilioValidationError, TwilioRateLimitError,
                TwilioAuthenticationError, TwilioPermissionError, TwilioResourceError):
            raise
        except Exception as e:
            logger.error(f"Failed to hangup call {call_sid}: {str(e)}")
            self._handle_twilio_exception(e)
            raise
