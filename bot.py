import os
from fastapi import FastAPI, Request
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API_URL = f"https://api.telegram.org/bot{TOKEN}"

app = FastAPI()

@app.get("/")
def alive():
    return {"status": "alive"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text.startswith("/start"):
            requests.post(
                f"{API_URL}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "✅ البوت يخدم توّا (نسخة بسيطة)"
                }
            )

    return {"ok": True}
