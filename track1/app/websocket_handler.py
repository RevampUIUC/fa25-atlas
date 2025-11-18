import os
import json
import base64
import logging
from datetime import datetime
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect
from app.deepgram_client import DeepgramTranscriber

logger = logging.getLogger(__name__)


class TwilioMediaStreamHandler:
    """Handle Twilio Media Stream WebSocket connections"""

    def __init__(self, db, websocket: WebSocket):
        """
        Initialize handler

        Args:
            db: MongoDB database instance
            websocket: FastAPI WebSocket connection
        """
        self.db = db
        self.websocket = websocket
        self.call_sid = None
        self.stream_sid = None
        self.transcriber = None
        self.call_start_time = None

    async def handle_connection(self):
        """Handle WebSocket connection lifecycle"""
        try:
            await self.websocket.accept()
            logger.info("WebSocket connection accepted")

            # Initialize Deepgram
            self.transcriber = DeepgramTranscriber()
            await self.transcriber.start_transcription(
                on_transcript=self.on_transcript_received,
                on_error=self.on_transcription_error
            )

            # Process messages
            while True:
                message = await self.websocket.receive_text()
                await self.process_message(message)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for call {self.call_sid}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self.cleanup()

    async def process_message(self, message: str):
        """
        Process incoming Twilio Media Stream message

        Args:
            message: JSON message from Twilio
        """
        try:
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                await self.handle_start(data)
            elif event == "media":
                await self.handle_media(data)
            elif event == "stop":
                await self.handle_stop(data)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def handle_start(self, data: Dict):
        """Handle stream start event"""
        self.stream_sid = data["streamSid"]
        self.call_sid = data["start"]["callSid"]
        self.call_start_time = datetime.utcnow()

        logger.info(f"Media stream started: {self.stream_sid} for call {self.call_sid}")

        # Update call record
        self.db.db.calls.update_one(
            {"call_sid": self.call_sid},
            {
                "$set": {
                    "stream_sid": self.stream_sid,
                    "transcription_started_at": self.call_start_time,
                    "updated_at": datetime.utcnow()
                }
            }
        )

    async def handle_media(self, data: Dict):
        """Handle incoming audio data"""
        if not self.transcriber or not self.transcriber.is_connected:
            return

        try:
            # Extract audio payload
            payload = data["media"]["payload"]
            
            # Decode base64 audio (mulaw format)
            audio_bytes = base64.b64decode(payload)
            
            # Send to Deepgram
            await self.transcriber.send_audio(audio_bytes)

        except Exception as e:
            logger.error(f"Error processing media: {e}")

    async def handle_stop(self, data: Dict):
        """Handle stream stop event"""
        logger.info(f"Media stream stopped: {self.stream_sid}")

        # Update call record
        self.db.db.calls.update_one(
            {"call_sid": self.call_sid},
            {
                "$set": {
                    "transcription_ended_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

    def on_transcript_received(self, result: Dict):
        """
        Callback when transcript is received from Deepgram

        Args:
            result: Transcript result with timestamps
        """
        try:
            if not result["is_final"]:
                return  # Only save final transcripts

            # Calculate absolute timestamp from call start
            call_offset_seconds = (datetime.utcnow() - self.call_start_time).total_seconds()

            # Save to database
            transcript_doc = {
                "call_sid": self.call_sid,
                "stream_sid": self.stream_sid,
                "transcript": result["transcript"],
                "is_final": result["is_final"],
                "speech_final": result["speech_final"],
                "words": result["words"],
                "call_offset_seconds": call_offset_seconds,
                "absolute_timestamp": datetime.utcnow(),
                "metadata": result["metadata"],
                "created_at": datetime.utcnow()
            }

            self.db.db.transcripts.insert_one(transcript_doc)
            logger.info(f"Saved transcript for call {self.call_sid}: {result['transcript']}")

        except Exception as e:
            logger.error(f"Error saving transcript: {e}")

    def on_transcription_error(self, error):
        """Handle transcription errors"""
        logger.error(f"Transcription error: {error}")

    async def cleanup(self):
        """Clean up resources"""
        if self.transcriber:
            await self.transcriber.close()