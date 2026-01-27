# ==============================
# SMART TRADING TELEGRAM BOT
# Safe • Professional • Realistic
# ==============================

import os
import asyncio
import logging
import time
from typing import Optional

import ccxt
import pandas as pd
import numpy as np

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("smartbot")

# ==============================
# ENV / SAFE START
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()

DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "bybit")
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1h")
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "200"))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ar")

# ==============================
# GLOBAL STATE (per user)
# ==============================
USER_STATE = {}

# ==============================
# EXCHANGE FACTORY (CCXT)
# ==============================
def get_exchange(name: str):
    name = name.lower()
    if not hasattr(ccxt, name):
        return None
    return getattr(ccxt, name)({
        "enableRateLimit": True,
    })

# ==============================
# MARKET DATA
# ==============================
def fetch_ohlcv(symbol: str, timeframe=DEFAULT_TIMEFRAME, limit=DEFAULT_LIMIT):
    exchange = get_exchange(DEFAULT_EXCHANGE)
    if not exchange:
        return None

    symbol = symbol.upper()
    if "/" not in symbol:
        symbol = symbol + "/USDT"

    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv,
            columns=["ts", "open", "high", "low", "close", "volume"],
        )
        return df
    except Exception as e:
        logger.error(f"Market data error: {e}")
        return None

# ==============================
# INDICATORS
# ==============================
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

# ==============================
# SIGNAL ENGINE (REALISTIC)
# ==============================
def generate_signal(df: pd.DataFrame):
    if df is None or len(df) < 50:
        return None

    close = df["close"]
    rsi_val = rsi(close).iloc[-1]
    ema50 = ema(close, 50).iloc[-1]
    ema200 = ema(close, 200).iloc[-1]
    price = close.iloc[-1]

    trend = "bullish" if ema50 > ema200 else "bearish"

    if trend == "bullish" and rsi_val < 35:
        side = "BUY"
    elif trend == "bearish" and rsi_val > 65:
        side = "SELL"
    else:
        return None

    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]

    if side == "BUY":
        entry = price
        sl = entry - atr
        tp = entry + (atr * 2)
    else:
        entry = price
        sl = entry + atr
        tp = entry - (atr * 2)

    rr = round(abs(tp - entry) / abs(entry - sl), 2)

    return {
        "side": side,
        "entry": round(entry, 4),
        "sl": round(sl, 4),
        "tp": round(tp, 4),
        "rr": rr,
        "trend": trend,
        "rsi": round(rsi_val, 2),
    }

# ==============================
# FORMATTERS
# ==============================
def format_signal(symbol: str, sig: dict, lang="ar"):
    if lang == "en":
        return (
            f"🎯 Signal ({symbol})\n\n"
            f"Side: {sig['side']}\n"
            f"Entry: {sig['entry']}\n"
            f"Stop Loss: {sig['sl']}\n"
            f"Take Profit: {sig['tp']}\n"
            f"Risk/Reward: {sig['rr']}\n\n"
            f"Trend: {sig['trend']} | RSI: {sig['rsi']}\n\n"
            f"⚠️ Educational – Not financial advice"
        )

    return (
        f"🎯 إشارة تداول ({symbol})\n\n"
        f"📌 النوع: {sig['side']}\n"
        f"🎯 الدخول: {sig['entry']}\n"
        f"🛑 الوقف: {sig['sl']}\n"
        f"🏁 الهدف: {sig['tp']}\n"
        f"⚖️ R/R: {sig['rr']}\n\n"
        f"📊 الاتجاه: {sig['trend']} | RSI: {sig['rsi']}\n\n"
        f"⚠️ محتوى تعليمي وليس نصيحة مالية"
    )

# ==============================
# UI
# ==============================
def main_keyboard(lang="ar"):
    if lang == "en":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Analysis", callback_data="analysis")],
            [InlineKeyboardButton("🎯 Signal", callback_data="signal")],
            [InlineKeyboardButton("🤖 Auto Paper", callback_data="paper")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        ])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تحليل", callback_data="analysis")],
        [InlineKeyboardButton("🎯 إشارة", callback_data="signal")],
        [InlineKeyboardButton("🤖 Auto Paper", callback_data="paper")],
        [InlineKeyboardButton("⚙️ إعدادات", callback_data="settings")],
    ])

# ==============================
# HANDLERS
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    USER_STATE[uid] = {
        "lang": DEFAULT_LANGUAGE,
        "symbol": None,
    }

    await update.message.reply_text(
        "🤖 Smart Trading Bot\nاختر من القائمة 👇",
        reply_markup=main_keyboard(),
    )

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    state = USER_STATE.get(uid, {})
    lang = state.get("lang", "ar")

    if query.data in ("analysis", "signal"):
        await query.message.reply_text(
            "أرسل الرمز مثل: BTC / ETH / XAUUSD"
            if lang == "ar"
            else "Send symbol like: BTC / ETH / XAUUSD"
        )
        state["mode"] = query.data
        USER_STATE[uid] = state

    elif query.data == "paper":
        await query.message.reply_text(
            "🤖 Auto Paper مفعل (محاكاة فقط)"
            if lang == "ar"
            else "🤖 Auto Paper enabled (simulation only)"
        )

    elif query.data == "settings":
        await query.message.reply_text(
            "⚙️ الإعدادات ستضاف لاحقًا"
            if lang == "ar"
            else "⚙️ Settings coming soon"
        )

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip().upper()

    state = USER_STATE.get(uid)
    if not state or "mode" not in state:
        return

    df = fetch_ohlcv(text)
    if df is None:
        await update.message.reply_text("❌ فشل جلب البيانات")
        return

    if state["mode"] == "analysis":
        await update.message.reply_text(
            f"📊 تحليل {text}\nآخر سعر: {df['close'].iloc[-1]:.4f}"
        )

    elif state["mode"] == "signal":
        sig = generate_signal(df)
        if not sig:
            await update.message.reply_text("⏸️ لا توجد فرصة واضحة الآن")
            return
        await update.message.reply_text(format_signal(text, sig, state["lang"]))

# ==============================
# MAIN
# ==============================
async def main():
    if not TELEGRAM_TOKEN:
        logger.error("⚠️ TELEGRAM_TOKEN غير موجود – البوت لن يبدأ")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("✅ Bot started safely")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
