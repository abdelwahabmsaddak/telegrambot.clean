import os
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -----------------------
# LOGGING
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("smartbot")

# -----------------------
# CONFIG (بدون كسر)
# -----------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()

DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "bybit")
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1h")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ar")

# -----------------------
# HANDLERS
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Smart Trading Bot\n\n"
        "• أسعار حية\n"
        "• فرص واقعية\n"
        "• Auto Paper\n\n"
        "اكتب الرمز مثل: BTC / ETH / XAUUSD"
    )

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.upper().strip()
    await update.message.reply_text(
        f"📊 استلمت الرمز: {text}\n"
        "⚙️ التحليل قيد التطوير..."
    )

# -----------------------
# MAIN (هنا فقط التحقق)
# -----------------------
async def main():
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN غير موجود في ENV")
        return   # ❗ لا نكسر Railway

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    logger.info("✅ Bot is running")
    await app.run_polling()

# -----------------------
# ENTRY POINT
# -----------------------
if __name__ == "__main__":
    asyncio.run(main())
