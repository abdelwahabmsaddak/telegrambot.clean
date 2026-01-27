import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import ccxt
import pandas as pd

# ---------------- LOGGING ----------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("smartbot")

# ---------------- ENV ----------------
TELEGRAM_TOKEN = (
    os.getenv("TELEGRAM_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
)

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN missing")

DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "bybit")
DEFAULT_TIMEFRAME = "1h"

# ---------------- EXCHANGE ----------------
exchange = ccxt.bybit({"enableRateLimit": True})

# ---------------- HELPERS ----------------
def fetch_ohlcv(symbol):
    data = exchange.fetch_ohlcv(symbol, timeframe=DEFAULT_TIMEFRAME, limit=200)
    df = pd.DataFrame(
        data, columns=["t", "o", "h", "l", "c", "v"]
    )
    return df

def signal(df):
    df["ma1"] = df["c"].rolling(9).mean()
    df["ma2"] = df["c"].rolling(21).mean()
    if df["ma1"].iloc[-1] > df["ma2"].iloc[-1]:
        return "BUY"
    if df["ma1"].iloc[-1] < df["ma2"].iloc[-1]:
        return "SELL"
    return "WAIT"

# ---------------- UI ----------------
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎯 إشارة", callback_data="signal")],
        [InlineKeyboardButton("🤖 Auto Paper", callback_data="paper")],
        [InlineKeyboardButton("🔍 Scan", callback_data="scan")],
    ])

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Smart Trading Bot شغّال\nاختار:",
        reply_markup=menu(),
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "analysis":
        await q.edit_message_text("أرسل رمز مثال: BTC/USDT")

    elif q.data == "signal":
        df = fetch_ohlcv("BTC/USDT")
        s = signal(df)
        await q.edit_message_text(
            f"🎯 BTC/USDT\nTF: {DEFAULT_TIMEFRAME}\nSignal: {s}"
        )

    elif q.data == "paper":
        await q.edit_message_text("🤖 Auto Paper مفعل (محاكاة)")

    elif q.data == "scan":
        symbols = list(exchange.load_markets().keys())[:20]
        buys = []
        for sym in symbols:
            try:
                df = fetch_ohlcv(sym)
                if signal(df) == "BUY":
                    buys.append(sym)
            except:
                pass

        await q.edit_message_text(
            "🔍 فرص:\n" + ("\n".join(buys) if buys else "لا فرص")
        )

# ---------------- START BOT ----------------
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler))

    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
