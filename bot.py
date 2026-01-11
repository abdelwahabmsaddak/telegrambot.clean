import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

app = FastAPI()

tg_app = Application.builder().token(TOKEN).build()

# 🔴 هذا هو السطر اللي كان ناقص شهر
@app.on_event("startup")
async def startup():
    await tg_app.initialize()
    await tg_app.start()

@app.on_event("shutdown")
async def shutdown():
    await tg_app.stop()
    await tg_app.shutdown()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت يخدم توّا")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

@app.get("/")
def root():
    return {"status": "alive"}
