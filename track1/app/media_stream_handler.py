import os
import logging
import json
import base64
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from app.deepgram_client import DeepgramSTTClient, TranscriptionSession

logger = logging.getLogger(__name__)


class TwilioMediaStreamHandler:
    """
    Handles Twilio Media Streams WebSocket connections
    Processes audio data and sends to Deepgram for transcription
    """

    def __init__(self, db):
        """
        Initialize media stream handler

        Args:
            db: Database instance
        """
        self.db = db
        self.active_sessions: Dict[str, TranscriptionSession] = {}

    async def handle_connection(self, websocket: WebSocket, call_sid: Optional[str] = None):
        """
        Handle WebSocket connection from Twilio Media Streams

        Args:
            websocket: FastAPI WebSocket connection
            call_sid: Optional Twilio call SID (can be extracted from stream)
        """
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for call: {call_sid}")

        stream_sid = None
        transcription_session = None

        try:
            # Create Deepgram client for this session
            deepgram_client = DeepgramSTTClient()

            while True:
                # Receive message from Twilio
                message = await websocket.receive_text()
                data = json.loads(message)

                event = data.get("event")

                if event == "start":
                    # Stream started
                    stream_sid = data["streamSid"]
                    start_data = data["start"]
                    call_sid = start_data["callSid"]

                    logger.info(
                        f"Media stream started - CallSid: {call_sid}, StreamSid: {stream_sid}"
                    )

                    # Create transcription session
                    transcription_session = TranscriptionSession(
                        call_sid=call_sid,
                        deepgram_client=deepgram_client,
                        db=self.db,
                    )

                    # Start Deepgram transcription
                    await transcription_session.start()

                    # Store active session
                    self.active_sessions[stream_sid] = transcription_session

                elif event == "media":
                    # Audio data received
                    if transcription_session and transcription_session.is_active:
                        # Extract audio payload
                        media = data["media"]
                        payload = media["payload"]

                        # Decode base64 mulaw audio
                        audio_data = base64.b64decode(payload)

                        # Send to Deepgram
                        await transcription_session.process_audio(audio_data)

                elif event == "stop":
                    # Stream stopped
                    logger.info(f"Media stream stopped - StreamSid: {stream_sid}")

                    # Stop transcription
                    if transcription_session:
                        await transcription_session.stop()

                    # Remove from active sessions
                    if stream_sid and stream_sid in self.active_sessions:
                        del self.active_sessions[stream_sid]

                    break

                elif event == "mark":
                    # Mark event (optional, used for synchronization)
                    mark_name = data.get("mark", {}).get("name")
                    logger.debug(f"Mark received: {mark_name}")

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for stream: {stream_sid}")
        except Exception as e:
            logger.error(f"Error in media stream handler: {str(e)}")
        finally:
            # Cleanup
            if transcription_session:
                try:
                    await transcription_session.stop()
                except:
                    pass

            if stream_sid and stream_sid in self.active_sessions:
                del self.active_sessions[stream_sid]

            logger.info(f"Media stream handler cleaned up for stream: {stream_sid}")

    def get_active_session(self, stream_sid: str) -> Optional[TranscriptionSession]:
        """
        Get active transcription session

        Args:
            stream_sid: Twilio stream SID

        Returns:
            TranscriptionSession if active, None otherwise
        """
        return self.active_sessions.get(stream_sid)

    def get_active_sessions_count(self) -> int:
        """Get count of active transcription sessions"""
        return len(self.active_sessions)
