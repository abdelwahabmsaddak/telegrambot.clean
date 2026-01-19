# bot.py
# -*- coding: utf-8 -*-

import os
import sys
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from ai_engine import ai_chat

# =========================
# Force UTF-8 (IMPORTANT)
# =========================
sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# =========================
# User Settings (simple)
# =========================
USERS = {}

def get_user(uid):
    if uid not in USERS:
        USERS[uid] = {"lang": "auto"}
    return USERS[uid]

# =========================
# Start Command
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📊 Analysis", "💬 Chat"],
        ["⚙️ Settings"]
    ]
    await update.message.reply_text(
        "🤖 AI Trading Bot Ready\n"
        "اسأل أي سؤال في التداول 👇",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# =========================
# Language Command
# =========================
async def lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)

    if not context.args:
        await update.message.reply_text("Use: /lang ar  or  /lang en")
        return

    if context.args[0].lower() in ["ar", "arabic"]:
        user["lang"] = "ar"
        await update.message.reply_text("✅ اللغة العربية مفعّلة")
    elif context.args[0].lower() in ["en", "english"]:
        user["lang"] = "en"
        await update.message.reply_text("✅ English enabled")
    else:
        await update.message.reply_text("❌ Unknown language")

# =========================
# Text Messages (AI CHAT)
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    text = update.message.text

    # clean & safe AI call
    reply = ai_chat(text, user["lang"])
    reply = reply.encode("utf-8", errors="ignore").decode("utf-8")

    await update.message.reply_text(reply)

# =========================
# Main
# =========================
def main():
    print("🤖 AI BOT RUNNING...")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", lang))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
