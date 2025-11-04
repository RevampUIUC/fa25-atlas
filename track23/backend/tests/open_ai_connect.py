import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
url = "https://api.openai.com/v1/models"
headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}"
}

response = requests.get(url, headers=headers)
print(response.status_code)
print(response.json())

