from dotenv import load_dotenv
import os
from pathlib import Path

# Load .env from the project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Optionally, handle missing values
if not (OPENAI_API_KEY and DEEPGRAM_API_KEY and ELEVENLABS_API_KEY):
    raise ValueError("Missing one or more required API keys in .env")