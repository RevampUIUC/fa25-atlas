import os
import logging
import asyncio
import json
from typing import Optional, Callable, Dict, Any
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)

logger = logging.getLogger(__name__)


class DeepgramSTTClient:
    """
    Deepgram Speech-to-Text client for real-time transcription
    Handles WebSocket connections and audio streaming
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Deepgram client

        Args:
            api_key: Deepgram API key (defaults to DEEPGRAM_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Missing required Deepgram configuration: DEEPGRAM_API_KEY"
            )

        # Initialize Deepgram client
        config = DeepgramClientOptions(
            options={"keepalive": "true"}
        )
        self.client = DeepgramClient(self.api_key, config)

        # Connection state
        self.connection = None
        self.is_connected = False

        # Callbacks for transcription events
        self.on_transcript_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None

        logger.info("Deepgram client initialized successfully")

    async def start_transcription(
        self,
        on_transcript: Callable[[str, Dict[str, Any]], None],
        on_error: Optional[Callable[[str], None]] = None,
        language: str = "en-US",
        model: str = "nova-2",
        punctuate: bool = True,
        interim_results: bool = True,
        smart_format: bool = True,
        utterance_end_ms: int = 1000,
    ) -> None:
        """
        Start a live transcription session

        Args:
            on_transcript: Callback function for transcript results
            on_error: Callback function for errors
            language: Language code (default: en-US)
            model: Deepgram model (default: nova-2)
            punctuate: Add punctuation (default: True)
            interim_results: Return interim results (default: True)
            smart_format: Smart formatting of output (default: True)
            utterance_end_ms: Milliseconds of silence to detect utterance end (default: 1000)
        """
        try:
            # Store callbacks
            self.on_transcript_callback = on_transcript
            self.on_error_callback = on_error

            # Configure live transcription options
            options = LiveOptions(
                language=language,
                model=model,
                punctuate=punctuate,
                interim_results=interim_results,
                smart_format=smart_format,
                utterance_end_ms=utterance_end_ms,
                # Twilio uses mulaw encoding at 8kHz
                encoding="mulaw",
                sample_rate=8000,
                channels=1,
            )

            # Create live transcription connection
            self.connection = self.client.listen.asyncwebsocket.v("1")

            # Register event handlers
            self.connection.on(LiveTranscriptionEvents.Open, self._on_open)
            self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
            self.connection.on(LiveTranscriptionEvents.Metadata, self._on_metadata)
            self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
            self.connection.on(LiveTranscriptionEvents.Close, self._on_close)

            # Start the connection
            if await self.connection.start(options):
                self.is_connected = True
                logger.info(
                    f"Deepgram live transcription started: model={model}, language={language}"
                )
            else:
                raise Exception("Failed to start Deepgram connection")

        except Exception as e:
            logger.error(f"Failed to start Deepgram transcription: {str(e)}")
            if self.on_error_callback:
                self.on_error_callback(str(e))
            raise

    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send audio data to Deepgram for transcription

        Args:
            audio_data: Raw audio bytes (mulaw format from Twilio)
        """
        try:
            if self.connection and self.is_connected:
                await self.connection.send(audio_data)
            else:
                logger.warning("Cannot send audio: Deepgram connection not established")
        except Exception as e:
            logger.error(f"Error sending audio to Deepgram: {str(e)}")
            if self.on_error_callback:
                self.on_error_callback(str(e))

    async def stop_transcription(self) -> None:
        """Stop the live transcription session"""
        try:
            if self.connection:
                await self.connection.finish()
                self.is_connected = False
                logger.info("Deepgram transcription stopped")
        except Exception as e:
            logger.error(f"Error stopping Deepgram transcription: {str(e)}")

    def _on_open(self, *args, **kwargs):
        """Handler for connection open event"""
        logger.info("Deepgram WebSocket connection opened")

    def _on_transcript(self, *args, **kwargs):
        """Handler for transcript events"""
        try:
            result = kwargs.get("result")
            if not result:
                return

            # Extract transcript information
            channel = result.channel
            if not channel or not channel.alternatives:
                return

            alternative = channel.alternatives[0]
            transcript = alternative.transcript

            if not transcript:
                return

            # Get metadata
            is_final = result.is_final
            speech_final = result.speech_final
            confidence = alternative.confidence if hasattr(alternative, 'confidence') else None

            # Prepare metadata
            metadata = {
                "is_final": is_final,
                "speech_final": speech_final,
                "confidence": confidence,
                "duration": result.duration if hasattr(result, 'duration') else None,
                "start": result.start if hasattr(result, 'start') else None,
            }

            # Log transcript
            status = "FINAL" if is_final else "INTERIM"
            logger.info(f"Transcript [{status}]: {transcript} (confidence: {confidence})")

            # Call user callback
            if self.on_transcript_callback:
                self.on_transcript_callback(transcript, metadata)

        except Exception as e:
            logger.error(f"Error processing transcript: {str(e)}")
            if self.on_error_callback:
                self.on_error_callback(str(e))

    def _on_metadata(self, *args, **kwargs):
        """Handler for metadata events"""
        metadata = kwargs.get("metadata")
        if metadata:
            logger.debug(f"Deepgram metadata: {metadata}")

    def _on_error(self, *args, **kwargs):
        """Handler for error events"""
        error = kwargs.get("error")
        error_msg = str(error) if error else "Unknown error"
        logger.error(f"Deepgram error: {error_msg}")

        if self.on_error_callback:
            self.on_error_callback(error_msg)

    def _on_close(self, *args, **kwargs):
        """Handler for connection close event"""
        self.is_connected = False
        logger.info("Deepgram WebSocket connection closed")


class TranscriptionSession:
    """
    Manages a single transcription session for a call
    Handles storing transcripts and managing the Deepgram connection
    """

    def __init__(
        self,
        call_sid: str,
        deepgram_client: DeepgramSTTClient,
        db,
    ):
        """
        Initialize transcription session

        Args:
            call_sid: Twilio call SID
            deepgram_client: Deepgram client instance
            db: Database instance
        """
        self.call_sid = call_sid
        self.deepgram_client = deepgram_client
        self.db = db
        self.transcripts = []
        self.is_active = False

    async def start(self) -> None:
        """Start the transcription session"""
        try:
            await self.deepgram_client.start_transcription(
                on_transcript=self._handle_transcript,
                on_error=self._handle_error,
            )
            self.is_active = True
            logger.info(f"Transcription session started for call: {self.call_sid}")
        except Exception as e:
            logger.error(f"Failed to start transcription session: {str(e)}")
            raise

    async def process_audio(self, audio_data: bytes) -> None:
        """
        Process audio data

        Args:
            audio_data: Raw audio bytes from Twilio
        """
        if self.is_active:
            await self.deepgram_client.send_audio(audio_data)

    async def stop(self) -> None:
        """Stop the transcription session"""
        try:
            await self.deepgram_client.stop_transcription()
            self.is_active = False
            logger.info(
                f"Transcription session stopped for call: {self.call_sid}. "
                f"Total transcripts: {len(self.transcripts)}"
            )
        except Exception as e:
            logger.error(f"Error stopping transcription session: {str(e)}")

    def _handle_transcript(self, transcript: str, metadata: Dict[str, Any]) -> None:
        """
        Handle transcript callback from Deepgram

        Args:
            transcript: Transcribed text
            metadata: Transcript metadata
        """
        try:
            # Only store final transcripts to database
            if metadata.get("is_final"):
                # Store to database
                from datetime import datetime

                self.db.save_transcript(
                    call_sid=self.call_sid,
                    speaker="caller",  # Can be enhanced with speaker diarization
                    text=transcript,
                    ts=datetime.utcnow()
                )

                # Keep in memory for session
                self.transcripts.append({
                    "transcript": transcript,
                    "metadata": metadata,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                logger.info(
                    f"Stored transcript for {self.call_sid}: {transcript[:100]}..."
                )

        except Exception as e:
            logger.error(f"Error handling transcript: {str(e)}")

    def _handle_error(self, error: str) -> None:
        """
        Handle error callback from Deepgram

        Args:
            error: Error message
        """
        logger.error(f"Transcription error for call {self.call_sid}: {error}")
