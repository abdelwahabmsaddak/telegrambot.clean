import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

app = FastAPI()
telegram_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت يخدم و يجاوب")

telegram_app.add_handler(CommandHandler("start", start))

@app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(
        url="https://telegrambotclean-openaiapikey.up.railway.app/webhook"
    )

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
