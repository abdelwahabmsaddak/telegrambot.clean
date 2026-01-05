import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ai_engine import ai_analyze
from trading import trade_signal

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 بوت تداول ذكي جاهز\n\n"
        "📝 اكتب:\n"
        "btc\neth\ngold"
    )

# أي رسالة نصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    if text in ["btc", "eth", "gold"]:
        signal = trade_signal(text.upper())
        analysis = ai_analyze(f"حلل {text.upper()} الآن")
        await update.message.reply_text(signal + "\n\n" + analysis)
    else:
        await update.message.reply_text("❓ اكتب: btc أو eth أو gold")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
