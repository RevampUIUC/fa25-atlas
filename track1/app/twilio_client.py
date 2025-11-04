import os
import logging
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


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

    def make_outbound_call(
        self,
        to_number: str,
        call_id: str,
        script: Optional[str] = None,
        recording_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call

        Args:
            to_number: Destination phone number
            call_id: Unique call identifier
            script: Optional TwiML script or URL
            recording_enabled: Whether to record the call

        Returns:
            Dict with call_sid and status
        """
        try:
            # Build the URL to fetch TwiML from our voice endpoint
            voice_url = f"{self.base_url}/twilio/voice?call_id={call_id}"

            # Add recording parameter if enabled
            if recording_enabled:
                voice_url += "&recording=true"

            call = self.client.calls.create(
                to=to_number,
                from_=self.from_number,
                url=voice_url,
                status_callback=f"{self.base_url}/twilio/status",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST",
            )

            logger.info(f"Outbound call initiated: {call.sid} to {to_number}")
            return {"call_sid": call.sid, "status": "initiated"}

        except Exception as e:
            logger.error(f"Failed to initiate outbound call: {str(e)}")
            raise

    def get_call_details(self, call_sid: str) -> Dict[str, Any]:
        """
        Get details of a specific call

        Args:
            call_sid: Twilio Call SID

        Returns:
            Dict with call details
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
        except Exception as e:
            logger.error(f"Failed to get call details for {call_sid}: {str(e)}")
            raise

    def generate_twiml_response(
        self,
        script: Optional[str] = None,
        record_call: bool = True,
    ) -> str:
        """
        Generate TwiML response for voice calls with consent message

        Args:
            script: Text to speak (speech synthesis)
            record_call: Whether to record the call

        Returns:
            TwiML response as string
        """
        response = VoiceResponse()

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
        except Exception as e:
            logger.error(f"Failed to get recording URL for {recording_sid}: {str(e)}")
            raise

    def hangup_call(self, call_sid: str) -> bool:
        """
        Terminate an active call

        Args:
            call_sid: Twilio Call SID

        Returns:
            True if successful
        """
        try:
            call = self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call terminated: {call.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to hangup call {call_sid}: {str(e)}")
            raise
