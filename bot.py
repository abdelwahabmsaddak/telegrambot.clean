import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

app = FastAPI()
tg_app = Application.builder().token(TOKEN).build()

@app.on_event("startup")
async def startup():
    await tg_app.initialize()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت يخدم توّا يا بطل")

tg_app.add_handler(CommandHandler("start", start))

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
