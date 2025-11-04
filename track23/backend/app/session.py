from typing import Dict, Any

# In-memory session store (not production-safe)
SESSIONS: Dict[str, Any] = {}

def create_session(session_id: str, data: Any):
    """Create a new session with data."""
    SESSIONS[session_id] = data

def get_session(session_id: str):
    """Retrieve session data by session_id."""
    return SESSIONS.get(session_id)

def session_exists(session_id: str) -> bool:
    """Check if a session exists for a session_id."""
    return session_id in SESSIONS

def delete_session(session_id: str):
    """Optional: Delete a session."""
    if session_id in SESSIONS:
        del SESSIONS[session_id]

