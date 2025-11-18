"""
Voicemail Detection System for Atlas

This module implements multi-signal voicemail detection using:
1. Twilio's answeredBy parameter (AMD - Answering Machine Detection)
2. Keyword/pattern matching from transcripts
3. Audio pattern heuristics (beep detection, silence patterns)
4. Deepgram transcript analysis
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class VoicemailSignal:
    """A single voicemail detection signal"""
    signal_type: str  # "amd", "keyword", "audio_pattern", "transcript_analysis"
    confidence: float  # 0.0 to 1.0
    detected_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VoicemailDetectionResult:
    """Result of voicemail detection analysis"""
    is_voicemail: bool
    confidence: float  # Overall confidence (0.0 to 1.0)
    signals: List[VoicemailSignal]
    detection_method: str  # Primary method used
    metadata: Dict[str, Any] = field(default_factory=dict)


class VoicemailPatterns:
    """Voicemail detection patterns and keywords"""

    # Common voicemail greeting phrases
    VOICEMAIL_KEYWORDS = [
        # Standard greetings
        "leave a message",
        "leave your message",
        "at the beep",
        "after the beep",
        "after the tone",
        "at the tone",
        "please record your message",
        "record your message",
        "unable to answer",
        "can't come to the phone",
        "cannot come to the phone",
        "not available",
        "away from my phone",
        "away from the phone",
        "can't take your call",
        "cannot take your call",
        "you have reached the voicemail",
        "you've reached the voicemail",
        "you have reached",
        "you've reached",

        # Carrier/system messages
        "the person you are calling",
        "the person you have called",
        "the subscriber you have dialed",
        "the number you have dialed",
        "the customer you are calling",
        "mailbox is full",
        "voicemail box",
        "voice mailbox",
        "to leave a callback number",
        "if you'd like to leave a message",
        "if you would like to leave a message",

        # Professional voicemail
        "out of the office",
        "out of office",
        "business hours",
        "office hours",
        "press pound",
        "press star",
        "press 1",
        "press 2",
    ]

    # Phrases that indicate a human answered
    HUMAN_INDICATORS = [
        "hello",
        "hi there",
        "good morning",
        "good afternoon",
        "good evening",
        "how can i help",
        "how may i help",
        "speaking",
        "this is",
        "yes",
        "yeah",
    ]

    # Regex patterns for voicemail detection
    VOICEMAIL_PATTERNS = [
        r"leave\s+(?:a\s+|your\s+)?message",
        r"after\s+the\s+(?:beep|tone)",
        r"at\s+the\s+(?:beep|tone)",
        r"(?:un)?able\s+to\s+(?:answer|take)",
        r"not\s+available",
        r"can'?t\s+(?:come\s+to|take)",
        r"you'?ve?\s+reached",
        r"voice\s*mail",
        r"mailbox",
        r"out\s+of\s+(?:the\s+)?office",
        r"business\s+hours",
        r"press\s+\d+",
    ]


class VoicemailDetector:
    """
    Multi-signal voicemail detection system

    Combines multiple detection methods:
    - Twilio AMD (answeredBy parameter)
    - Transcript keyword matching
    - Audio pattern analysis
    - ML-based classification (future)
    """

    def __init__(
        self,
        amd_confidence_threshold: float = 0.85,
        keyword_confidence_threshold: float = 0.75,
        min_signals_required: int = 1,
        enable_aggressive_detection: bool = False
    ):
        """
        Initialize voicemail detector

        Args:
            amd_confidence_threshold: Minimum confidence for AMD detection
            keyword_confidence_threshold: Minimum confidence for keyword detection
            min_signals_required: Minimum number of signals needed to confirm voicemail
            enable_aggressive_detection: Enable more aggressive detection (higher false positives)
        """
        self.amd_confidence_threshold = amd_confidence_threshold
        self.keyword_confidence_threshold = keyword_confidence_threshold
        self.min_signals_required = min_signals_required
        self.enable_aggressive_detection = enable_aggressive_detection

        # Statistics for accuracy tracking
        self.detection_stats = {
            "total_analyzed": 0,
            "voicemail_detected": 0,
            "human_detected": 0,
            "uncertain": 0,
            "methods_used": {
                "amd": 0,
                "keyword": 0,
                "audio_pattern": 0,
                "transcript_analysis": 0
            }
        }

    def analyze_call(
        self,
        call_sid: str,
        answered_by: Optional[str] = None,
        transcripts: Optional[List[Dict]] = None,
        call_duration: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> VoicemailDetectionResult:
        """
        Analyze a call to detect if it reached voicemail

        Args:
            call_sid: Twilio Call SID
            answered_by: Twilio's answeredBy parameter value
            transcripts: List of transcript documents from database
            call_duration: Call duration in seconds
            metadata: Additional metadata (audio patterns, etc.)

        Returns:
            VoicemailDetectionResult with detection confidence and signals
        """
        self.detection_stats["total_analyzed"] += 1
        signals = []

        # Signal 1: Twilio AMD (answeredBy parameter)
        if answered_by:
            amd_signal = self._analyze_amd(answered_by)
            if amd_signal:
                signals.append(amd_signal)
                self.detection_stats["methods_used"]["amd"] += 1

        # Signal 2: Transcript keyword analysis
        if transcripts:
            keyword_signal = self._analyze_transcript_keywords(transcripts)
            if keyword_signal:
                signals.append(keyword_signal)
                self.detection_stats["methods_used"]["keyword"] += 1

            # Signal 3: Deepgram transcript analysis (timing, confidence patterns)
            transcript_signal = self._analyze_transcript_patterns(transcripts)
            if transcript_signal:
                signals.append(transcript_signal)
                self.detection_stats["methods_used"]["transcript_analysis"] += 1

        # Signal 4: Audio pattern heuristics
        if metadata:
            audio_signal = self._analyze_audio_patterns(metadata, call_duration)
            if audio_signal:
                signals.append(audio_signal)
                self.detection_stats["methods_used"]["audio_pattern"] += 1

        # Combine signals to make final decision
        result = self._combine_signals(call_sid, signals, metadata or {})

        # Update statistics
        if result.is_voicemail:
            self.detection_stats["voicemail_detected"] += 1
        elif result.confidence < 0.3:
            self.detection_stats["uncertain"] += 1
        else:
            self.detection_stats["human_detected"] += 1

        logger.info(
            f"Voicemail detection for {call_sid}: "
            f"is_voicemail={result.is_voicemail}, "
            f"confidence={result.confidence:.2f}, "
            f"method={result.detection_method}, "
            f"signals={len(signals)}"
        )

        return result

    def _analyze_amd(self, answered_by: str) -> Optional[VoicemailSignal]:
        """
        Analyze Twilio's answeredBy parameter

        Twilio AMD can return:
        - "human" - A human answered
        - "machine_start" - Answering machine detected (beginning of greeting)
        - "machine_end_beep" - Answering machine detected (beep detected)
        - "machine_end_silence" - Answering machine detected (silence after greeting)
        - "machine_end_other" - Answering machine detected (other pattern)
        - "fax" - Fax machine detected
        - "unknown" - Could not determine

        Args:
            answered_by: Twilio's answeredBy value

        Returns:
            VoicemailSignal if voicemail detected, None otherwise
        """
        answered_by_lower = answered_by.lower()

        if answered_by_lower == "human":
            return None  # Human answered, not voicemail

        if "machine" in answered_by_lower:
            # Determine confidence based on detection type
            confidence = 0.95  # Default high confidence

            if answered_by_lower == "machine_end_beep":
                confidence = 0.98  # Highest confidence - beep detected
            elif answered_by_lower == "machine_start":
                confidence = 0.90  # Good confidence - start of greeting
            elif answered_by_lower == "machine_end_silence":
                confidence = 0.92  # Good confidence - silence after greeting
            elif answered_by_lower == "machine_end_other":
                confidence = 0.85  # Lower confidence - other pattern

            if confidence >= self.amd_confidence_threshold:
                return VoicemailSignal(
                    signal_type="amd",
                    confidence=confidence,
                    detected_at=datetime.utcnow(),
                    details={
                        "answered_by": answered_by,
                        "detection_type": answered_by_lower
                    }
                )

        elif answered_by_lower == "fax":
            # Fax machine - treat as machine but lower confidence for voicemail
            return VoicemailSignal(
                signal_type="amd",
                confidence=0.70,
                detected_at=datetime.utcnow(),
                details={
                    "answered_by": answered_by,
                    "detection_type": "fax"
                }
            )

        return None

    def _analyze_transcript_keywords(
        self,
        transcripts: List[Dict]
    ) -> Optional[VoicemailSignal]:
        """
        Analyze transcripts for voicemail keywords and phrases

        Args:
            transcripts: List of transcript documents

        Returns:
            VoicemailSignal if voicemail keywords detected
        """
        if not transcripts:
            return None

        # Combine all transcript text (first 60 seconds most important)
        first_60_sec = []
        all_text = []

        for transcript in transcripts:
            text = transcript.get("text", "").lower()
            ts_offset = transcript.get("start_offset", 0)

            all_text.append(text)
            if ts_offset <= 60:
                first_60_sec.append(text)

        combined_text = " ".join(all_text)
        early_text = " ".join(first_60_sec)

        # Check for voicemail keywords
        voicemail_matches = []
        human_matches = []

        for keyword in VoicemailPatterns.VOICEMAIL_KEYWORDS:
            if keyword in early_text or keyword in combined_text:
                weight = 2.0 if keyword in early_text else 1.0
                voicemail_matches.append((keyword, weight))

        # Check regex patterns
        for pattern in VoicemailPatterns.VOICEMAIL_PATTERNS:
            if re.search(pattern, early_text, re.IGNORECASE):
                voicemail_matches.append((pattern, 2.0))
            elif re.search(pattern, combined_text, re.IGNORECASE):
                voicemail_matches.append((pattern, 1.0))

        # Check for human indicators (should be absent or minimal)
        for indicator in VoicemailPatterns.HUMAN_INDICATORS:
            if indicator in early_text:
                human_matches.append(indicator)

        # Calculate confidence
        if not voicemail_matches:
            return None

        # Scoring algorithm
        voicemail_score = sum(weight for _, weight in voicemail_matches)
        human_penalty = len(human_matches) * 0.5

        # Normalize to 0-1 scale
        raw_confidence = min(voicemail_score / 5.0, 1.0)
        adjusted_confidence = max(0.0, raw_confidence - (human_penalty * 0.1))

        if adjusted_confidence >= self.keyword_confidence_threshold:
            return VoicemailSignal(
                signal_type="keyword",
                confidence=adjusted_confidence,
                detected_at=datetime.utcnow(),
                details={
                    "matched_keywords": [kw for kw, _ in voicemail_matches],
                    "keyword_count": len(voicemail_matches),
                    "human_indicators": human_matches,
                    "voicemail_score": voicemail_score,
                    "human_penalty": human_penalty
                }
            )

        return None

    def _analyze_transcript_patterns(
        self,
        transcripts: List[Dict]
    ) -> Optional[VoicemailSignal]:
        """
        Analyze transcript timing and confidence patterns

        Voicemail characteristics:
        - Usually starts immediately (0-2 seconds)
        - Monologue (single speaker, no back-and-forth)
        - Consistent high confidence (pre-recorded)
        - Fixed duration (typically 15-45 seconds)
        - May end with beep sound or silence

        Args:
            transcripts: List of transcript documents

        Returns:
            VoicemailSignal if patterns match voicemail
        """
        if not transcripts or len(transcripts) < 3:
            return None  # Not enough data

        # Analyze speaker patterns
        speakers = set()
        first_speaker_time = None
        speaker_changes = 0
        last_speaker = None

        # Analyze timing and confidence
        confidences = []
        start_times = []

        for transcript in transcripts:
            speaker = transcript.get("speaker", "unknown")
            confidence = transcript.get("confidence", 0)
            start_offset = transcript.get("start_offset", 0)

            speakers.add(speaker)
            confidences.append(confidence)
            start_times.append(start_offset)

            if first_speaker_time is None:
                first_speaker_time = start_offset

            if last_speaker and last_speaker != speaker:
                speaker_changes += 1
            last_speaker = speaker

        # Pattern checks
        patterns_matched = []

        # Pattern 1: Single speaker (monologue)
        if len(speakers) == 1 and speaker_changes == 0:
            patterns_matched.append(("monologue", 0.3))

        # Pattern 2: Starts very quickly (< 2 seconds)
        if first_speaker_time is not None and first_speaker_time < 2.0:
            patterns_matched.append(("immediate_start", 0.2))

        # Pattern 3: High average confidence (pre-recorded = clearer)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        if avg_confidence > 0.95:
            patterns_matched.append(("high_confidence", 0.2))

        # Pattern 4: Consistent confidence (low variance)
        if len(confidences) > 1:
            confidence_variance = sum((c - avg_confidence) ** 2 for c in confidences) / len(confidences)
            if confidence_variance < 0.01:  # Very low variance
                patterns_matched.append(("consistent_confidence", 0.15))

        # Pattern 5: Short duration (typical voicemail 15-45 seconds)
        if start_times:
            max_time = max(start_times)
            if 15 <= max_time <= 45:
                patterns_matched.append(("typical_duration", 0.15))

        # Calculate overall confidence from patterns
        if not patterns_matched:
            return None

        pattern_confidence = sum(score for _, score in patterns_matched)

        if pattern_confidence >= 0.4:  # At least 2-3 patterns matched
            return VoicemailSignal(
                signal_type="transcript_analysis",
                confidence=min(pattern_confidence, 0.95),
                detected_at=datetime.utcnow(),
                details={
                    "patterns_matched": [name for name, _ in patterns_matched],
                    "speaker_count": len(speakers),
                    "speaker_changes": speaker_changes,
                    "avg_confidence": avg_confidence,
                    "duration": max(start_times) if start_times else 0
                }
            )

        return None

    def _analyze_audio_patterns(
        self,
        metadata: Dict,
        call_duration: Optional[int]
    ) -> Optional[VoicemailSignal]:
        """
        Analyze audio patterns and heuristics

        Looks for:
        - Beep detection
        - Silence patterns
        - Audio quality consistency
        - One-way audio

        Args:
            metadata: Call metadata with audio analysis
            call_duration: Call duration in seconds

        Returns:
            VoicemailSignal if audio patterns match voicemail
        """
        patterns_detected = []

        # Check for beep detection (if available in metadata)
        if metadata.get("beep_detected"):
            patterns_detected.append(("beep_detected", 0.4))

        # Check for silence after greeting
        silence_duration = metadata.get("trailing_silence_duration", 0)
        if silence_duration > 3:  # More than 3 seconds of silence
            patterns_detected.append(("trailing_silence", 0.3))

        # Check for one-way audio (no input from caller)
        if metadata.get("one_way_audio", False):
            patterns_detected.append(("one_way_audio", 0.2))

        # Short call duration (< 60 seconds often indicates voicemail)
        if call_duration and call_duration < 60:
            patterns_detected.append(("short_duration", 0.15))

        if not patterns_detected:
            return None

        audio_confidence = sum(score for _, score in patterns_detected)

        if audio_confidence >= 0.3:
            return VoicemailSignal(
                signal_type="audio_pattern",
                confidence=min(audio_confidence, 0.9),
                detected_at=datetime.utcnow(),
                details={
                    "patterns_detected": [name for name, _ in patterns_detected],
                    "beep_detected": metadata.get("beep_detected", False),
                    "silence_duration": silence_duration,
                    "call_duration": call_duration
                }
            )

        return None

    def _combine_signals(
        self,
        call_sid: str,
        signals: List[VoicemailSignal],
        metadata: Dict
    ) -> VoicemailDetectionResult:
        """
        Combine multiple signals into final detection result

        Uses weighted voting and confidence aggregation

        Args:
            call_sid: Call SID
            signals: List of detection signals
            metadata: Additional metadata

        Returns:
            VoicemailDetectionResult
        """
        if not signals:
            return VoicemailDetectionResult(
                is_voicemail=False,
                confidence=0.0,
                signals=[],
                detection_method="none",
                metadata={"call_sid": call_sid, "reason": "no_signals"}
            )

        # Weight signals by type (AMD is most reliable)
        signal_weights = {
            "amd": 1.0,              # Highest weight - Twilio's detection
            "keyword": 0.8,           # High weight - Direct evidence
            "transcript_analysis": 0.6,  # Medium weight - Pattern-based
            "audio_pattern": 0.5      # Lower weight - Heuristic
        }

        # Calculate weighted confidence
        total_weight = 0.0
        weighted_confidence = 0.0

        for signal in signals:
            weight = signal_weights.get(signal.signal_type, 0.5)
            total_weight += weight
            weighted_confidence += signal.confidence * weight

        overall_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.0

        # Determine primary detection method (highest confidence signal)
        primary_signal = max(signals, key=lambda s: s.confidence)
        detection_method = primary_signal.signal_type

        # Decision logic
        is_voicemail = False

        if self.enable_aggressive_detection:
            # Aggressive mode: Any single strong signal triggers detection
            is_voicemail = overall_confidence >= 0.6 or any(s.confidence >= 0.85 for s in signals)
        else:
            # Conservative mode: Require either high overall confidence or multiple signals
            if overall_confidence >= 0.75:
                is_voicemail = True
            elif len(signals) >= self.min_signals_required and overall_confidence >= 0.6:
                is_voicemail = True
            elif any(s.signal_type == "amd" and s.confidence >= 0.9 for s in signals):
                # AMD with very high confidence is sufficient
                is_voicemail = True

        return VoicemailDetectionResult(
            is_voicemail=is_voicemail,
            confidence=overall_confidence,
            signals=signals,
            detection_method=detection_method,
            metadata={
                "call_sid": call_sid,
                "signal_count": len(signals),
                "signal_types": [s.signal_type for s in signals],
                "weighted_confidence": overall_confidence,
                "primary_method": detection_method,
                **metadata
            }
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get detection statistics for accuracy metrics

        Returns:
            Dict with detection statistics
        """
        total = self.detection_stats["total_analyzed"]
        if total == 0:
            return {
                "total_analyzed": 0,
                "accuracy_metrics": "insufficient_data"
            }

        return {
            "total_analyzed": total,
            "voicemail_detected": self.detection_stats["voicemail_detected"],
            "human_detected": self.detection_stats["human_detected"],
            "uncertain": self.detection_stats["uncertain"],
            "voicemail_rate": self.detection_stats["voicemail_detected"] / total,
            "human_rate": self.detection_stats["human_detected"] / total,
            "uncertain_rate": self.detection_stats["uncertain"] / total,
            "methods_used": self.detection_stats["methods_used"],
            "primary_method": max(
                self.detection_stats["methods_used"].items(),
                key=lambda x: x[1]
            )[0] if any(self.detection_stats["methods_used"].values()) else "none"
        }

    def reset_statistics(self):
        """Reset detection statistics"""
        self.detection_stats = {
            "total_analyzed": 0,
            "voicemail_detected": 0,
            "human_detected": 0,
            "uncertain": 0,
            "methods_used": {
                "amd": 0,
                "keyword": 0,
                "audio_pattern": 0,
                "transcript_analysis": 0
            }
        }
