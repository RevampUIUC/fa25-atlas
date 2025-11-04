from dotenv import load_dotenv
import os
import requests

load_dotenv()
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

url = "https://api.deepgram.com/v1/projects"
headers = {
    "Authorization": f"Token {DEEPGRAM_API_KEY}"
}

response = requests.get(url, headers=headers)
print(response.status_code)
print(response.json())
