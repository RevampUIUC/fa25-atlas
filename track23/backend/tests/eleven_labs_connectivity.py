from dotenv import load_dotenv
import os
import requests

load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

url = "https://api.elevenlabs.io/v1/models"
headers = {
    "xi-api-key": ELEVENLABS_API_KEY
}

response = requests.get(url, headers=headers)
print(response.status_code)
print(response.json())
