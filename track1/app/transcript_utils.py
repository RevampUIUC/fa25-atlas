"""
Transcript serialization, deserialization, and utility functions
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)


class TranscriptSerializer:
    """Serializes transcript data for storage and export"""

    @staticmethod
    def to_database(
        call_sid: str,
        speaker: str,
        text: str,
        ts: datetime,
        confidence: Optional[float] = None,
        duration: Optional[float] = None,
        start_offset: Optional[float] = None,
        end_offset: Optional[float] = None,
        is_final: bool = True,
        language: str = "en-US",
        words: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Serialize transcript for database storage

        Args:
            call_sid: Twilio Call SID
            speaker: Speaker identifier
            text: Transcript text
            ts: Timestamp when spoken
            confidence: Confidence score (0.0-1.0)
            duration: Duration in seconds
            start_offset: Start offset from call start
            end_offset: End offset from call start
            is_final: Whether this is final transcript
            language: Language code
            words: Word-level data
            metadata: Additional metadata
            user_id: User ID reference

        Returns:
            Dictionary ready for MongoDB insertion
        """
        doc = {
            "call_sid": call_sid,
            "speaker": speaker,
            "text": text,
            "ts": ts,
            "is_final": is_final,
            "language": language,
            "created_at": datetime.utcnow()
        }

        # Add optional fields only if provided
        if user_id:
            doc["user_id"] = user_id

        if confidence is not None:
            doc["confidence"] = float(confidence)

        if duration is not None:
            doc["duration"] = float(duration)

        if start_offset is not None:
            doc["start_offset"] = float(start_offset)

        if end_offset is not None:
            doc["end_offset"] = float(end_offset)

        if words:
            doc["words"] = words

        if metadata:
            doc["metadata"] = metadata

        return doc

    @staticmethod
    def from_deepgram(
        call_sid: str,
        deepgram_result: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert Deepgram API response to database format

        Args:
            call_sid: Twilio Call SID
            deepgram_result: Deepgram transcript result
            user_id: User ID reference

        Returns:
            Dictionary ready for database storage
        """
        # Extract channel data
        channel = deepgram_result.get("channel", {})
        alternatives = channel.get("alternatives", [])

        if not alternatives:
            raise ValueError("No alternatives in Deepgram result")

        alternative = alternatives[0]

        # Extract words if available
        words = None
        if "words" in alternative:
            words = [
                {
                    "word": w.get("word"),
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "confidence": w.get("confidence"),
                    "punctuated_word": w.get("punctuated_word")
                }
                for w in alternative.get("words", [])
            ]

        # Build metadata
        metadata = {
            "provider": "deepgram",
            "speech_final": deepgram_result.get("speech_final", False)
        }

        # Determine speaker (can be enhanced with diarization)
        speaker = "caller"  # Default, can be determined from channel or diarization

        return TranscriptSerializer.to_database(
            call_sid=call_sid,
            speaker=speaker,
            text=alternative.get("transcript", ""),
            ts=datetime.utcnow(),
            confidence=alternative.get("confidence"),
            duration=deepgram_result.get("duration"),
            start_offset=deepgram_result.get("start"),
            is_final=deepgram_result.get("is_final", True),
            language=deepgram_result.get("language", "en-US"),
            words=words,
            metadata=metadata,
            user_id=user_id
        )

    @staticmethod
    def to_json(
        transcript_doc: Dict[str, Any],
        pretty: bool = False
    ) -> str:
        """
        Serialize transcript to JSON string

        Args:
            transcript_doc: Transcript document from database
            pretty: Whether to pretty-print JSON

        Returns:
            JSON string
        """
        # Convert ObjectId and datetime to strings
        doc = transcript_doc.copy()

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        if "user_id" in doc:
            doc["user_id"] = str(doc["user_id"])

        if "ts" in doc and isinstance(doc["ts"], datetime):
            doc["ts"] = doc["ts"].isoformat()

        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()

        if "indexed_at" in doc and isinstance(doc["indexed_at"], datetime):
            doc["indexed_at"] = doc["indexed_at"].isoformat()

        indent = 2 if pretty else None
        return json.dumps(doc, indent=indent)

    @staticmethod
    def to_export_format(
        call_sid: str,
        transcripts: List[Dict[str, Any]],
        call_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create export format for full call transcript

        Args:
            call_sid: Twilio Call SID
            transcripts: List of transcript documents
            call_metadata: Optional call metadata

        Returns:
            Export format dictionary
        """
        # Sort transcripts by timestamp
        sorted_transcripts = sorted(
            transcripts,
            key=lambda t: t.get("ts", datetime.min)
        )

        # Calculate statistics
        total_words = sum(
            len(t.get("text", "").split()) for t in transcripts
        )

        confidences = [
            t.get("confidence") for t in transcripts
            if t.get("confidence") is not None
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else None

        languages = list(set(t.get("language") for t in transcripts if t.get("language")))
        speakers = list(set(t.get("speaker") for t in transcripts if t.get("speaker")))

        export_doc = {
            "version": "1.0",
            "schema": "transcript_export/v1",
            "call": {
                "call_sid": call_sid,
                **(call_metadata or {})
            },
            "metadata": {
                "total_utterances": len(transcripts),
                "total_words": total_words,
                "average_confidence": round(avg_confidence, 4) if avg_confidence else None,
                "languages": languages,
                "speakers": speakers
            },
            "transcripts": [
                {
                    "speaker": t.get("speaker"),
                    "text": t.get("text"),
                    "ts": t.get("ts").isoformat() if isinstance(t.get("ts"), datetime) else t.get("ts"),
                    "confidence": t.get("confidence"),
                    "offset": t.get("start_offset")
                }
                for t in sorted_transcripts
            ],
            "exported_at": datetime.utcnow().isoformat()
        }

        return export_doc


class TranscriptQuery:
    """Helper class for querying transcripts"""

    @staticmethod
    def by_call(
        db,
        call_sid: str,
        final_only: bool = True,
        min_confidence: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all transcripts for a call

        Args:
            db: Database instance
            call_sid: Twilio Call SID
            final_only: Return only final transcripts
            min_confidence: Minimum confidence threshold

        Returns:
            List of transcript documents
        """
        query = {"call_sid": call_sid}

        if final_only:
            query["is_final"] = True

        if min_confidence is not None:
            query["confidence"] = {"$gte": min_confidence}

        return list(
            db.transcripts.find(query).sort("ts", 1)
        )

    @staticmethod
    def by_user(
        db,
        user_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get transcripts for a user

        Args:
            db: Database instance
            user_id: User ID
            limit: Maximum results
            skip: Number to skip

        Returns:
            List of transcript documents
        """
        return list(
            db.transcripts
            .find({"user_id": user_id})
            .sort("ts", -1)
            .skip(skip)
            .limit(limit)
        )

    @staticmethod
    def search_text(
        db,
        search_query: str,
        call_sid: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Full-text search transcripts

        Args:
            db: Database instance
            search_query: Search query
            call_sid: Optional call SID to filter
            limit: Maximum results

        Returns:
            List of matching transcript documents
        """
        query = {"$text": {"$search": search_query}}

        if call_sid:
            query["call_sid"] = call_sid

        return list(
            db.transcripts
            .find(query, {"score": {"$meta": "textScore"}})
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )

    @staticmethod
    def get_call_summary(
        db,
        call_sid: str
    ) -> Dict[str, Any]:
        """
        Get aggregated summary for a call

        Args:
            db: Database instance
            call_sid: Twilio Call SID

        Returns:
            Summary dictionary
        """
        pipeline = [
            {"$match": {"call_sid": call_sid, "is_final": True}},
            {
                "$group": {
                    "_id": "$call_sid",
                    "total_transcripts": {"$sum": 1},
                    "total_text": {"$push": "$text"},
                    "speakers": {"$addToSet": "$speaker"},
                    "languages": {"$addToSet": "$language"},
                    "avg_confidence": {"$avg": "$confidence"},
                    "min_confidence": {"$min": "$confidence"},
                    "max_confidence": {"$max": "$confidence"},
                    "first_ts": {"$min": "$ts"},
                    "last_ts": {"$max": "$ts"}
                }
            }
        ]

        result = list(db.transcripts.aggregate(pipeline))

        if not result:
            return {}

        summary = result[0]

        # Calculate total words
        total_words = sum(len(text.split()) for text in summary.get("total_text", []))

        # Calculate duration
        first_ts = summary.get("first_ts")
        last_ts = summary.get("last_ts")
        duration_sec = (last_ts - first_ts).total_seconds() if first_ts and last_ts else None

        return {
            "call_sid": call_sid,
            "total_transcripts": summary.get("total_transcripts", 0),
            "total_words": total_words,
            "speakers": summary.get("speakers", []),
            "languages": summary.get("languages", []),
            "avg_confidence": round(summary.get("avg_confidence", 0), 4),
            "min_confidence": round(summary.get("min_confidence", 0), 4),
            "max_confidence": round(summary.get("max_confidence", 0), 4),
            "duration_sec": duration_sec,
            "first_ts": first_ts,
            "last_ts": last_ts
        }


class TranscriptFormatter:
    """Format transcripts for display"""

    @staticmethod
    def to_text(
        transcripts: List[Dict[str, Any]],
        include_timestamps: bool = True,
        include_speaker: bool = True,
        include_confidence: bool = False
    ) -> str:
        """
        Format transcripts as plain text

        Args:
            transcripts: List of transcript documents
            include_timestamps: Include timestamps
            include_speaker: Include speaker labels
            include_confidence: Include confidence scores

        Returns:
            Formatted text string
        """
        lines = []

        for t in sorted(transcripts, key=lambda x: x.get("ts", datetime.min)):
            parts = []

            if include_timestamps:
                ts = t.get("ts")
                if isinstance(ts, datetime):
                    parts.append(f"[{ts.strftime('%H:%M:%S')}]")
                elif isinstance(ts, str):
                    parts.append(f"[{ts}]")

            if include_speaker:
                speaker = t.get("speaker", "unknown")
                parts.append(f"{speaker.upper()}:")

            if include_confidence:
                conf = t.get("confidence")
                if conf is not None:
                    parts.append(f"({conf:.2f})")

            parts.append(t.get("text", ""))

            lines.append(" ".join(parts))

        return "\n".join(lines)

    @staticmethod
    def to_html(
        transcripts: List[Dict[str, Any]],
        include_confidence: bool = True
    ) -> str:
        """
        Format transcripts as HTML

        Args:
            transcripts: List of transcript documents
            include_confidence: Include confidence scores

        Returns:
            HTML string
        """
        html_parts = ['<div class="transcript">']

        for t in sorted(transcripts, key=lambda x: x.get("ts", datetime.min)):
            ts = t.get("ts")
            ts_str = ts.strftime("%H:%M:%S") if isinstance(ts, datetime) else str(ts)

            speaker = t.get("speaker", "unknown")
            text = t.get("text", "")
            confidence = t.get("confidence")

            confidence_class = ""
            if confidence is not None:
                if confidence >= 0.9:
                    confidence_class = "high-confidence"
                elif confidence >= 0.7:
                    confidence_class = "medium-confidence"
                else:
                    confidence_class = "low-confidence"

            html_parts.append(f'<div class="utterance {confidence_class}">')
            html_parts.append(f'  <span class="timestamp">{ts_str}</span>')
            html_parts.append(f'  <span class="speaker">{speaker}:</span>')
            html_parts.append(f'  <span class="text">{text}</span>')

            if include_confidence and confidence is not None:
                html_parts.append(f'  <span class="confidence">({confidence:.2f})</span>')

            html_parts.append('</div>')

        html_parts.append('</div>')

        return "\n".join(html_parts)

    @staticmethod
    def to_markdown(
        transcripts: List[Dict[str, Any]],
        title: Optional[str] = None
    ) -> str:
        """
        Format transcripts as Markdown

        Args:
            transcripts: List of transcript documents
            title: Optional title

        Returns:
            Markdown string
        """
        lines = []

        if title:
            lines.append(f"# {title}")
            lines.append("")

        for t in sorted(transcripts, key=lambda x: x.get("ts", datetime.min)):
            ts = t.get("ts")
            ts_str = ts.strftime("%H:%M:%S") if isinstance(ts, datetime) else str(ts)

            speaker = t.get("speaker", "unknown")
            text = t.get("text", "")
            confidence = t.get("confidence")

            line = f"**[{ts_str}] {speaker.upper()}:** {text}"

            if confidence is not None:
                line += f" *({confidence:.2f})*"

            lines.append(line)
            lines.append("")

        return "\n".join(lines)
