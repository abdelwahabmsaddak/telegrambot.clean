import os
import asyncio
import logging
from datetime import datetime

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

# ---------------------------
# LOGGING
# ---------------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("smartbot")

# ---------------------------
# ENV
# ---------------------------
TELEGRAM_TOKEN = (
    os.getenv("TELEGRAM_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
)

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN missing in ENV")

DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "bybit")
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1h")
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "200"))

# ---------------------------
# EXCHANGES (PUBLIC ONLY)
# ---------------------------
EXCHANGES = {
    "bybit": ccxt.bybit({"enableRateLimit": True}),
    "okx": ccxt.okx({"enableRateLimit": True}),
    # Binance intentionally NOT default (451 issues)
}

# ---------------------------
# HELPERS
# ---------------------------
def get_exchange(name: str):
    if name not in EXCHANGES:
        raise ValueError("Exchange not supported")
    return EXCHANGES[name]

def fetch_ohlcv(exchange, symbol, timeframe, limit):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(
        data,
        columns=["time", "open", "high", "low", "close", "volume"],
    )
    return df

def simple_signal(df: pd.DataFrame):
    df["ma_fast"] = df["close"].rolling(9).mean()
    df["ma_slow"] = df["close"].rolling(21).mean()

    if df["ma_fast"].iloc[-1] > df["ma_slow"].iloc[-1]:
        return "BUY"
    if df["ma_fast"].iloc[-1] < df["ma_slow"].iloc[-1]:
        return "SELL"
    return "WAIT"

# ---------------------------
# UI
# ---------------------------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎯 إشارة", callback_data="signal")],
        [InlineKeyboardButton("🤖 Auto Paper", callback_data="paper")],
        [InlineKeyboardButton("🔍 Scan", callback_data="scan")],
        [InlineKeyboardButton("⚙️ إعدادات", callback_data="settings")],
    ])

# ---------------------------
# HANDLERS
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Smart Trading Bot جاهز للعمل\nاختر من القائمة:",
        reply_markup=main_menu(),
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "analysis":
        await query.edit_message_text(
            "أرسل الرمز مثال:\nBTC/USDT",
        )

    elif query.data == "signal":
        symbol = "BTC/USDT"
        exchange = get_exchange(DEFAULT_EXCHANGE)
        df = fetch_ohlcv(exchange, symbol, DEFAULT_TIMEFRAME, DEFAULT_LIMIT)
        sig = simple_signal(df)

        await query.edit_message_text(
            f"🎯 إشارة حالية\n"
            f"Symbol: {symbol}\n"
            f"Timeframe: {DEFAULT_TIMEFRAME}\n"
            f"Signal: {sig}"
        )

    elif query.data == "paper":
        await query.edit_message_text(
            "🤖 Auto Paper\n"
            "تم التفعيل (محاكاة بدون أموال)"
        )

    elif query.data == "scan":
        exchange = get_exchange(DEFAULT_EXCHANGE)
        markets = list(exchange.load_markets().keys())[:10]

        results = []
        for sym in markets:
            try:
                df = fetch_ohlcv(exchange, sym, DEFAULT_TIMEFRAME, 100)
                sig = simple_signal(df)
                if sig == "BUY":
                    results.append(sym)
            except Exception:
                continue

        text = "🔍 Scan Results:\n"
        text += "\n".join(results) if results else "لا فرص حالياً"

        await query.edit_message_text(text)

    elif query.data == "settings":
        await query.edit_message_text(
            f"⚙️ الإعدادات الحالية:\n"
            f"Exchange: {DEFAULT_EXCHANGE}\n"
            f"Timeframe: {DEFAULT_TIMEFRAME}"
        )

# ---------------------------
# MAIN
# ---------------------------
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler))

    logger.info("Bot started")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
