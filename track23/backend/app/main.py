from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.chat import chat_router

app = FastAPI()

# Allow frontend dev server (adjust if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # or your frontend's address
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/chat")

# Temporary root endpoint (for testing the server)
@app.get("/")
def read_root():
    return {"message": "FastAPI backend is running!"}


