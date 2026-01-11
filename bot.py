import os
from fastapi import FastAPI, Request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

app = FastAPI()
bot = Bot(token=TOKEN)

application = Application.builder().token(TOKEN).build()

# ====== Handlers ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 البوت يخدم توّا، مرحبا بيك!")

application.add_handler(CommandHandler("start", start))

# ====== Routes ======
@app.get("/")
async def root():
    return {"status": "alive"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return {"ok": True}
