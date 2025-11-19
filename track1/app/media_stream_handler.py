import os
import logging
import json
import base64
import asyncio
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from app.deepgram_client import DeepgramTranscriber

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
        self.active_sessions: Dict[str, DeepgramTranscriber] = {}

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
        deepgram_client = None
        call_start_time = datetime.utcnow()

        try:
            # Create Deepgram client for this session
            deepgram_client = DeepgramTranscriber()

            # Define callback to save transcripts
            def on_transcript(result):
                try:
                    if call_sid and result.get("transcript"):
                        # Calculate offset from call start
                        offset_seconds = (datetime.utcnow() - call_start_time).total_seconds()

                        # Save transcript to database
                        transcript_doc = {
                            "call_sid": call_sid,
                            "stream_sid": stream_sid,
                            "transcript": result["transcript"],
                            "is_final": result.get("is_final", False),
                            "speech_final": result.get("speech_final", False),
                            "words": result.get("words", []),
                            "call_offset_seconds": offset_seconds,
                            "absolute_timestamp": datetime.utcnow(),
                            "speaker": None,  # Speaker diarization not implemented yet
                        }

                        self.db.db.transcripts.insert_one(transcript_doc)
                        logger.info(f"Saved transcript for call {call_sid}: {result['transcript'][:50]}...")
                except Exception as e:
                    logger.error(f"Error saving transcript: {e}")

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
                    call_start_time = datetime.utcnow()

                    logger.info(
                        f"Media stream started - CallSid: {call_sid}, StreamSid: {stream_sid}"
                    )

                    # Start Deepgram transcription
                    await deepgram_client.start_transcription(
                        on_transcript=on_transcript,
                        on_error=lambda e: logger.error(f"Deepgram error: {e}"),
                    )

                    # Store active session
                    self.active_sessions[stream_sid] = deepgram_client

                elif event == "media":
                    # Audio data received
                    if deepgram_client and deepgram_client.is_connected:
                        # Extract audio payload
                        media = data["media"]
                        payload = media["payload"]

                        # Decode base64 mulaw audio
                        audio_data = base64.b64decode(payload)

                        # Send to Deepgram
                        await deepgram_client.send_audio(audio_data)

                elif event == "stop":
                    # Stream stopped
                    logger.info(f"Media stream stopped - StreamSid: {stream_sid}")

                    # Stop transcription
                    if deepgram_client:
                        await deepgram_client.close()

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
            if deepgram_client:
                try:
                    await deepgram_client.close()
                except:
                    pass

            if stream_sid and stream_sid in self.active_sessions:
                del self.active_sessions[stream_sid]

            logger.info(f"Media stream handler cleaned up for stream: {stream_sid}")

    def get_active_session(self, stream_sid: str) -> Optional[DeepgramTranscriber]:
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
