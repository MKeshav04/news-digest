import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

payload = {
    "chat_id": CHAT_ID,
    "text": "Hello from my news digest bot.",
}

response = requests.post(url, data=payload)

print(response.status_code)
print(response.json())
