# -*- coding: utf-8 -*-

import os
import sys
import io
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ai_engine import ai_chat
from utils import safe_text

# ===== UTF-8 FIX (مهم جدا) =====
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN not set")


# ===== Commands =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 Smart Trading Bot\n\n"
        "اكتب أي سؤال تداول:\n"
        "BTC / ETH / GOLD / أسهم\n\n"
        "أو اسأل بالعربي أو بالإنجليزي."
    )
    await update.message.reply_text(msg)


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        reply = ai_chat(user_text)
        await update.message.reply_text(safe_text(reply))
    except Exception as e:
        logging.exception("AI ERROR")
        await update.message.reply_text(
            "❌ حصل خطأ في الذكاء الاصطناعي. حاول لاحقًا."
        )


# ===== Main =====
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("🤖 AI BOT RUNNING...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
