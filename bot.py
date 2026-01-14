print("BOT FILE LOADED")

import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def echo(update: Update, context):
    await update.message.reply_text("📩 وصلني مساجك")

app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, echo))

print("RUNNING POLLING")
app.run_polling()
