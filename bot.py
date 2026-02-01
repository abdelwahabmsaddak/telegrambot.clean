import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ======================
# جلب السعر
# ======================
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    r = requests.get(url, timeout=10)
    data = r.json()
    return float(data["price"])

# ======================
# start
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 سعر العملات", callback_data="prices")],
        [InlineKeyboardButton("📊 معلومات البوت", callback_data="info")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 مرحبا بك\n\n"
        "هذا بوت أسعار العملات الرقمية\n"
        "اختر من القائمة 👇",
        reply_markup=reply_markup,
    )

# ======================
# الأزرار
# ======================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "prices":
        btc = get_price("BTCUSDT")
        eth = get_price("ETHUSDT")
        bnb = get_price("BNBUSDT")

        text = (
            "💰 أسعار العملات:\n\n"
            f"🟠 BTC: {btc:.2f} $\n"
            f"🔵 ETH: {eth:.2f} $\n"
            f"🟡 BNB: {bnb:.2f} $\n"
        )

        await query.edit_message_text(text)

    elif query.data == "info":
        await query.edit_message_text(
            "📊 معلومات البوت\n\n"
            "- يجلب الأسعار مباشرة\n"
            "- بدون تداول آلي\n"
            "- العميل يقرر بنفسه\n"
            "- البوت مستقر وموثوق ✅"
        )

# ======================
# main
# ======================
def main():
    if not TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN غير موجود")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 البوت يعمل ...")
    app.run_polling()

if __name__ == "__main__":
    main()
