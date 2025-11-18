import os
import logging
from typing import Optional, Dict, Any, Callable

try:
    # Try new import path (SDK 3.x+)
    from deepgram import DeepgramClient, DeepgramClientOptions
    from deepgram.clients.live.v1 import LiveOptions
    from deepgram.clients.live.enums import LiveTranscriptionEvents
except ImportError:
    # Fallback to old import path (SDK 2.x)
    from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

logger = logging.getLogger(__name__)


class DeepgramTranscriber:
    """Deepgram real-time transcription client"""

    def __init__(self, api_key: str = None):
        """
        Initialize Deepgram client

        Args:
            api_key: Deepgram API key
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY configuration")

        try:
            # Try new SDK initialization (3.x+)
            config = DeepgramClientOptions(api_key=self.api_key)
            self.client = DeepgramClient(self.api_key, config)
        except:
            # Fallback to old SDK initialization (2.x)
            self.client = DeepgramClient(self.api_key)
        
        self.connection = None
        self.is_connected = False

    async def start_transcription(
        self,
        on_transcript: Callable,
        on_error: Callable = None,
        language: str = "en-US",
        model: str = "nova-2",
    ):
        """
        Start real-time transcription

        Args:
            on_transcript: Callback for transcript results
            on_error: Callback for errors
            language: Language code
            model: Deepgram model
        """
        try:
            # Configure transcription options
            options = LiveOptions(
                model=model,
                language=language,
                smart_format=True,
                punctuate=True,
                interim_results=True,
                utterance_end_ms=1000,
                vad_events=True,
                encoding="mulaw",
                sample_rate=8000,
                channels=1,
            )

            # Create connection
            try:
                # Try new SDK method (3.x+)
                self.connection = self.client.listen.asynclive.v("1")
            except:
                # Fallback to old SDK method (2.x)
                self.connection = self.client.listen.asyncwebsocket.v("1")

            # Set up event handlers
            @self.connection.on(LiveTranscriptionEvents.Transcript)
            def on_message(self_inner, result, **kwargs):
                """Handle transcript results"""
                try:
                    sentence = result.channel.alternatives[0].transcript
                    if len(sentence) > 0:
                        # Extract metadata
                        is_final = result.is_final
                        speech_final = result.speech_final
                        
                        # Extract word-level timestamps
                        words = []
                        if hasattr(result.channel.alternatives[0], 'words'):
                            for word in result.channel.alternatives[0].words:
                                words.append({
                                    "word": word.word,
                                    "start": word.start,
                                    "end": word.end,
                                    "confidence": word.confidence
                                })

                        # Call user's callback
                        on_transcript({
                            "transcript": sentence,
                            "is_final": is_final,
                            "speech_final": speech_final,
                            "words": words,
                            "metadata": {
                                "request_id": result.metadata.request_id if hasattr(result, 'metadata') else None,
                                "model_info": result.metadata.model_info if hasattr(result, 'metadata') else None,
                            }
                        })
                except Exception as e:
                    logger.error(f"Error processing transcript: {e}")
                    if on_error:
                        on_error(e)

            @self.connection.on(LiveTranscriptionEvents.Error)
            def on_error_event(self_inner, error, **kwargs):
                """Handle errors"""
                logger.error(f"Deepgram error: {error}")
                if on_error:
                    on_error(error)

            @self.connection.on(LiveTranscriptionEvents.Close)
            def on_close(self_inner, close, **kwargs):
                """Handle connection close"""
                logger.info("Deepgram connection closed")
                self.is_connected = False

            # Start connection
            if await self.connection.start(options):
                logger.info("Deepgram transcription started")
                self.is_connected = True
                return True
            else:
                logger.error("Failed to start Deepgram connection")
                return False

        except Exception as e:
            logger.error(f"Failed to start transcription: {e}")
            if on_error:
                on_error(e)
            return False

    async def send_audio(self, audio_data: bytes):
        """
        Send audio data for transcription

        Args:
            audio_data: Raw audio bytes (mulaw, 8kHz)
        """
        if self.connection and self.is_connected:
            try:
                await self.connection.send(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio: {e}")

    async def close(self):
        """Close the transcription connection"""
        if self.connection:
            try:
                await self.connection.finish()
                self.is_connected = False
                logger.info("Deepgram connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")