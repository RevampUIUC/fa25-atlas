"""
No-Answer Detection Configuration
Week 3: Call Intelligence
"""

# Timeout thresholds for no-answer detection
NO_ANSWER_TIMEOUT_SECONDS = 30  # Consider no-answer after 30 seconds of ringing

# Retry configuration for no-answer scenarios
NO_ANSWER_MAX_RETRIES = 3
NO_ANSWER_RETRY_DELAYS = [2, 5, 10]  # minutes between retries

# Statuses that indicate no-answer
NO_ANSWER_STATUSES = ["no-answer", "busy"]

# Voicemail detection keywords (for future enhancement)
VOICEMAIL_KEYWORDS = [
    "voicemail",
    "leave a message",
    "not available",
    "after the beep",
    "mailbox"
]