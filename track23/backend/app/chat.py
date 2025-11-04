from fastapi import APIRouter, Body
from app.session import create_session, session_exists, get_session

chat_router = APIRouter()

@chat_router.post("/")
async def chat(message: dict = Body(...)):
    session_id = message.get("session_id")
    user_message = message.get("content")

    # Create session if it doesn't exist
    if not session_exists(session_id):
        create_session(session_id, {"messages": []})

    # Retrieve and update session data
    session_data = get_session(session_id)
    session_data["messages"].append(user_message)

    # Here, process the message as needed (currently, just echoing back)
    return {
        "session_id": session_id,
        "response": f"Echo: {user_message}"
    }
