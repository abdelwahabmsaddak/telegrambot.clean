# -*- coding: utf-8 -*-
import os
import time
import math
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import ccxt
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()  # optional (AI explanation)
DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "binance").strip().lower()

# Auto-scan symbols (you can change)
DEFAULT_WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XAUUSD"]  # XAUUSD uses fallback note

# =========================
# Simple in-memory user store (production: use DB)
# =========================
USERS: Dict[int, Dict[str, Any]] = {}

def uget(chat_id: int) -> Dict[str, Any]:
    if chat_id not in USERS:
        USERS[chat_id] = {
            "mode": "chat",                # chat | analysis | signal | settings | paper
            "symbol": None,                # e.g. BTC/USDT
            "auto_on": False,              # auto trading toggle
            "paper_on": False,             # auto paper toggle
            "exchange": DEFAULT_EXCHANGE,  # binance/bybit/okx...
            "api_key": None,
            "api_secret": None,
            "risk_pct": 1.0,               # percent risk per trade
            "capital": 1000.0,             # virtual/paper capital
            "last_signal_ts": 0,
        }
    return USERS[chat_id]

# =========================
# Indicators
# =========================
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / (loss.replace(0, np.nan))
    return 100 - (100 / (1 + rs))

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# =========================
# Exchange / Market data
# =========================
def get_exchange(name: str, api_key: Optional[str] = None, api_secret: Optional[str] = None):
    name = (name or "binance").lower()
    if not hasattr(ccxt, name):
        name = "binance"
    ex_class = getattr(ccxt, name)
    params = {"enableRateLimit": True}
    if api_key and api_secret:
        params.update({"apiKey": api_key, "secret": api_secret})
    return ex_class(params)

def fetch_ohlcv(symbol: str, exchange_name: str, timeframe: str = "15m", limit: int = 200) -> pd.DataFrame:
    ex = get_exchange(exchange_name)
    # CCXT symbols like BTC/USDT. For XAUUSD: not supported on many spot exchanges.
    if symbol.upper() == "XAUUSD":
        raise ValueError("XAUUSD not supported via spot CCXT in this demo. Use a broker/CFD feed later.")
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

def fetch_live_price(symbol: str, exchange_name: str) -> float:
    ex = get_exchange(exchange_name)
    if symbol.upper() == "XAUUSD":
        raise ValueError("XAUUSD not supported in this demo feed.")
    t = ex.fetch_ticker(symbol)
    return float(t["last"])

# =========================
# Chart generator
# =========================
def make_chart(df: pd.DataFrame, symbol: str) -> str:
    # Simple price + EMA chart
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)

    fig = plt.figure(figsize=(10, 5))
    plt.plot(df["ts"], df["close"], label="Close")
    plt.plot(df["ts"], df["ema20"], label="EMA20")
    plt.plot(df["ts"], df["ema50"], label="EMA50")
    plt.title(f"{symbol} - 15m")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.legend()
    plt.tight_layout()

    out = f"/tmp/chart_{symbol.replace('/', '_')}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out

# =========================
# Signal logic (realistic + numbers)
# =========================
@dataclass
class Signal:
    side: str  # BUY / SELL / WAIT
    entry: Tuple[float, float]
    sl: float
    tp1: float
    tp2: float
    rr: float
    confidence: int
    reason: str

def build_signal(df: pd.DataFrame) -> Signal:
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi14"] = rsi(df["close"], 14)
    df["atr14"] = atr(df, 14)

    last = df.iloc[-1]
    price = float(last["close"])
    e20 = float(last["ema20"])
    e50 = float(last["ema50"])
    r = float(last["rsi14"]) if not math.isnan(float(last["rsi14"])) else 50.0
    a = float(last["atr14"]) if not math.isnan(float(last["atr14"])) else (price * 0.003)

    trend_up = e20 > e50
    trend_down = e20 < e50

    # Entry zone near EMA20
    zone_low = e20 * 0.998
    zone_high = e20 * 1.002

    # Basic logic:
    # BUY if uptrend + RSI not overheated + price near EMA20
    # SELL if downtrend + RSI not oversold + price near EMA20
    side = "WAIT"
    reason = []
    conf = 50

    if trend_up and (45 <= r <= 70) and (zone_low <= price <= zone_high):
        side = "BUY"
        reason.append("Uptrend (EMA20 > EMA50)")
        reason.append("Price near EMA20 (pullback zone)")
        reason.append(f"RSI={r:.1f} (not overheated)")
        conf = 75
    elif trend_down and (30 <= r <= 55) and (zone_low <= price <= zone_high):
        side = "SELL"
        reason.append("Downtrend (EMA20 < EMA50)")
        reason.append("Price near EMA20 (pullback zone)")
        reason.append(f"RSI={r:.1f} (not oversold)")
        conf = 72
    else:
        # Explain why wait
        if trend_up:
            reason.append("Trend up لكن الدخول ليس في منطقة pullback")
        elif trend_down:
            reason.append("Trend down لكن الدخول ليس في منطقة pullback")
        else:
            reason.append("السوق جانبي (EMA20 قريب من EMA50)")
        reason.append(f"RSI={r:.1f}")
        conf = 55

    # Build levels using ATR
    entry = (round(zone_low, 4), round(zone_high, 4))
    if side == "BUY":
        sl = price - (1.5 * a)
        tp1 = price + (2.0 * a)
        tp2 = price + (3.2 * a)
    elif side == "SELL":
        sl = price + (1.5 * a)
        tp1 = price - (2.0 * a)
        tp2 = price - (3.2 * a)
    else:
        sl = price - (1.5 * a)
        tp1 = price + (2.0 * a)
        tp2 = price + (3.2 * a)

    risk = abs(price - sl)
    reward = abs(tp1 - price)
    rr = (reward / risk) if risk > 0 else 0.0

    return Signal(
        side=side,
        entry=(float(entry[0]), float(entry[1])),
        sl=float(round(sl, 4)),
        tp1=float(round(tp1, 4)),
        tp2=float(round(tp2, 4)),
        rr=float(round(rr, 2)),
        confidence=int(conf),
        reason="; ".join(reason),
    )

def format_signal(symbol: str, price: float, sig: Signal) -> str:
    return (
        f"🎯 SIGNAL - {symbol}\n\n"
        f"💰 السعر الحالي: {price:.4f}\n"
        f"📌 القرار: {sig.side}\n\n"
        f"🎯 Entry Zone: {sig.entry[0]:.4f} - {sig.entry[1]:.4f}\n"
        f"🛑 Stop Loss: {sig.sl:.4f}\n"
        f"✅ TP1: {sig.tp1:.4f}\n"
        f"✅ TP2: {sig.tp2:.4f}\n"
        f"⚖️ R:R: {sig.rr}\n"
        f"🤖 Confidence: {sig.confidence}%\n\n"
        f"🧠 السبب: {sig.reason}\n\n"
        f"⚠️ تنبيه: هذا تحليل تعليمي. لا يوجد ضمان ربح."
    )

# =========================
# Trading (real execution) - spot only (no leverage)
# =========================
def calc_position_size(capital: float, risk_pct: float, entry_price: float, sl_price: float) -> float:
    risk_amount = capital * (risk_pct / 100.0)
    per_unit_risk = abs(entry_price - sl_price)
    if per_unit_risk <= 0:
        return 0.0
    qty = risk_amount / per_unit_risk
    # For spot, qty is base amount (BTC). This is simplified.
    return float(qty)

async def place_order_real(user: Dict[str, Any], symbol: str, side: str, qty: float) -> str:
    if not user.get("api_key") or not user.get("api_secret"):
        return "❌ API Key/Secret غير موجود. ادخلهم من Settings."
    ex = get_exchange(user["exchange"], user["api_key"], user["api_secret"])
    # Market order (simple)
    try:
        if side == "BUY":
            o = ex.create_market_buy_order(symbol, qty)
        elif side == "SELL":
            o = ex.create_market_sell_order(symbol, qty)
        else:
            return "❌ لا يوجد أمر."
        oid = o.get("id", "ok")
        return f"✅ تم تنفيذ أمر {side} (Market) | qty={qty:.6f} | id={oid}"
    except Exception as e:
        return f"❌ فشل التنفيذ: {str(e)}"

# =========================
# Minimal AI explainer (works without OpenAI too)
# =========================
async def ai_explain(text: str) -> str:
    # If you later want real OpenAI calls, we add them safely.
    # For now: always return helpful explanation without needing credit.
    return (
        "🧠 تفسير سريع (Smart):\n"
        "- هذا القرار مبني على اتجاه EMA + منطقة Pullback + RSI.\n"
        "- الأفضل تنفذ فقط لما السعر يدخل Entry Zone.\n"
        "- لا ترفع المخاطرة فوق 1-2%.\n"
        "- إذا السوق سريع بزاف: خفف حجم الصفقة.\n\n"
        "إذا تحب، نزيدك Plan دخول/خروج خطوة بخطوة حسب نفس الرمز."
    )

# =========================
# UI / Keyboards
# =========================
def main_kb(chat_id: int) -> InlineKeyboardMarkup:
    user = uget(chat_id)
    auto = "✅ Auto ON" if user["auto_on"] else "🤖 Auto OFF"
    paper = "✅ Paper ON" if user["paper_on"] else "🧾 Paper OFF"
    rows = [
        [InlineKeyboardButton("📊 Analysis", callback_data="mode:analysis"),
         InlineKeyboardButton("🎯 Signal", callback_data="mode:signal")],
        [InlineKeyboardButton(auto, callback_data="toggle:auto"),
         InlineKeyboardButton(paper, callback_data="toggle:paper")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="mode:settings"),
         InlineKeyboardButton("💬 Chat", callback_data="mode:chat")],
    ]
    return InlineKeyboardMarkup(rows)

def settings_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🏦 Exchange", callback_data="set:exchange"),
         InlineKeyboardButton("🔑 API Key/Secret", callback_data="set:api")],
        [InlineKeyboardButton("💰 Capital", callback_data="set:capital"),
         InlineKeyboardButton("⚖️ Risk %", callback_data="set:risk")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back:main")],
    ]
    return InlineKeyboardMarkup(rows)

# =========================
# Handlers
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = uget(chat_id)
    text = (
        "🤖 Smart Trading Bot (Realistic)\n\n"
        "اختر وضع:\n"
        "- Analysis: تحليل مع رسم + مستويات\n"
        "- Signal: إشارة بأرقام Entry/SL/TP + ثقة\n"
        "- Auto: تنفيذ حقيقي (يحتاج API) أو Paper\n\n"
        "ارسل رمز مثل: BTC/USDT أو ETH/USDT\n"
        "ملاحظة: XAUUSD سنضيف له مزود بيانات لاحقا."
    )
    await update.message.reply_text(text, reply_markup=main_kb(chat_id))

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = uget(chat_id)
    data = query.data

    if data.startswith("mode:"):
        user["mode"] = data.split(":", 1)[1]
        if user["mode"] == "settings":
            await query.edit_message_text("⚙️ Settings:", reply_markup=settings_kb())
        else:
            await query.edit_message_text(
                f"✅ تم اختيار: {user['mode'].upper()}\nارسل الرمز مثل BTC/USDT",
                reply_markup=main_kb(chat_id),
            )
        return

    if data == "toggle:auto":
        user["auto_on"] = not user["auto_on"]
        await query.edit_message_reply_markup(reply_markup=main_kb(chat_id))
        return

    if data == "toggle:paper":
        user["paper_on"] = not user["paper_on"]
        await query.edit_message_reply_markup(reply_markup=main_kb(chat_id))
        return

    if data == "back:main":
        await query.edit_message_text("✅ رجعنا للقائمة.", reply_markup=main_kb(chat_id))
        return

    # settings actions
    if data == "set:exchange":
        user["pending"] = "exchange"
        await query.edit_message_text(
            "🏦 اكتب اسم المنصة (binance / bybit / okx / kucoin ...):",
            reply_markup=settings_kb(),
        )
        return

    if data == "set:api":
        user["pending"] = "api"
        await query.edit_message_text(
            "🔑 ارسل هكذا في رسالة واحدة:\nAPI_KEY,API_SECRET\n\n"
            "⚠️ عطّل Withdraw من المنصة.",
            reply_markup=settings_kb(),
        )
        return

    if data == "set:capital":
        user["pending"] = "capital"
        await query.edit_message_text("💰 اكتب رأس المال (مثلا 1000):", reply_markup=settings_kb())
        return

    if data == "set:risk":
        user["pending"] = "risk"
        await query.edit_message_text("⚖️ اكتب نسبة المخاطرة % (مثلا 1 أو 2):", reply_markup=settings_kb())
        return

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = uget(chat_id)
    msg = (update.message.text or "").strip()

    # Settings input
    if user.get("pending"):
        p = user["pending"]
        user["pending"] = None

        if p == "exchange":
            user["exchange"] = msg.lower()
            await update.message.reply_text(f"✅ تم ضبط Exchange: {user['exchange']}", reply_markup=main_kb(chat_id))
            return

        if p == "api":
            try:
                k, s = [x.strip() for x in msg.split(",", 1)]
                user["api_key"] = k
                user["api_secret"] = s
                await update.message.reply_text("✅ تم حفظ API. (تأكد Withdraw OFF)", reply_markup=main_kb(chat_id))
            except:
                await update.message.reply_text("❌ صيغة خاطئة. ارسل: API_KEY,API_SECRET", reply_markup=main_kb(chat_id))
            return

        if p == "capital":
            try:
                user["capital"] = float(msg)
                await update.message.reply_text(f"✅ Capital: {user['capital']}", reply_markup=main_kb(chat_id))
            except:
                await update.message.reply_text("❌ اكتب رقم فقط.", reply_markup=main_kb(chat_id))
            return

        if p == "risk":
            try:
                user["risk_pct"] = float(msg)
                await update.message.reply_text(f"✅ Risk%: {user['risk_pct']}", reply_markup=main_kb(chat_id))
            except:
                await update.message.reply_text("❌ اكتب رقم فقط.", reply_markup=main_kb(chat_id))
            return

    # Normal flow: treat as symbol or chat
    # Accept forms: BTC or BTC/USDT
    symbol = msg.upper().replace(" ", "")
    if "/" not in symbol and symbol.isalnum():
        # default quote
        symbol = f"{symbol}/USDT"

    user["symbol"] = symbol

    # Run according to mode
    mode = user["mode"]

    # XAUUSD note
    if symbol == "XAUUSD":
        await update.message.reply_text(
            "⚠️ XAUUSD يحتاج مزود بيانات (Broker/CFD). حاليا هذا البوت يدعم Spot Crypto عبر CCXT.\n"
            "نضيف الذهب لاحقا بمزود صحيح.",
            reply_markup=main_kb(chat_id),
        )
        return

    try:
        df = fetch_ohlcv(symbol, user["exchange"], timeframe="15m", limit=220)
        live = fetch_live_price(symbol, user["exchange"])
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ جلب البيانات: {str(e)}", reply_markup=main_kb(chat_id))
        return

    sig = build_signal(df)

    if mode == "analysis":
        chart_path = make_chart(df.tail(200), symbol)
        text = (
            f"📊 Analysis - {symbol}\n\n"
            f"💰 السعر الحالي: {live:.4f}\n"
            f"📌 الاتجاه (تقريبا): {'صاعد' if ema(df['close'],20).iloc[-1] > ema(df['close'],50).iloc[-1] else 'هابط/جانبي'}\n"
            f"🤖 خلاصة: {sig.side} | ثقة {sig.confidence}%\n\n"
            f"🎯 Zone: {sig.entry[0]:.4f} - {sig.entry[1]:.4f}\n"
            f"🛑 SL: {sig.sl:.4f}\n"
            f"✅ TP1: {sig.tp1:.4f}\n"
            f"✅ TP2: {sig.tp2:.4f}\n"
        )
        await update.message.reply_photo(photo=open(chart_path, "rb"), caption=text)
        exp = await ai_explain(text)
        await update.message.reply_text(exp, reply_markup=main_kb(chat_id))
        return

    if mode == "signal":
        text = format_signal(symbol, live, sig)
        await update.message.reply_text(text, reply_markup=main_kb(chat_id))

        # Paper/Auto execution (ONLY if side BUY/SELL and price inside entry zone)
        inside = (sig.entry[0] <= live <= sig.entry[1])
        if sig.side in ["BUY", "SELL"] and inside and (user["paper_on"] or user["auto_on"]):
            # position size
            qty = calc_position_size(user["capital"], user["risk_pct"], live, sig.sl)
            if qty <= 0:
                await update.message.reply_text("❌ حجم الصفقة صفر. راجع Capital/Risk.", reply_markup=main_kb(chat_id))
                return

            if user["paper_on"] and not user["auto_on"]:
                await update.message.reply_text(
                    f"🧾 PAPER EXECUTED: {sig.side} {symbol}\nqty={qty:.6f}\n"
                    f"Entry~{live:.4f} | SL={sig.sl:.4f} | TP1={sig.tp1:.4f}",
                    reply_markup=main_kb(chat_id),
                )
                return

            if user["auto_on"]:
                res = await place_order_real(user, symbol, sig.side, qty)
                await update.message.reply_text(res, reply_markup=main_kb(chat_id))
                return
        return

    # chat mode: helpful answer
    await update.message.reply_text(
        "💬 اكتب الرمز (BTC/USDT) ثم اختر Analysis أو Signal.\n"
        "إذا تحب Auto Trading: ادخل API من Settings ثم Auto ON.",
        reply_markup=main_kb(chat_id),
    )

# =========================
# Auto scanner loop (optional)
# =========================
async def auto_loop(app: Application):
    while True:
        try:
            for chat_id, user in list(USERS.items()):
                if not user.get("paper_on") and not user.get("auto_on"):
                    continue

                # throttle
                if time.time() - user.get("last_signal_ts", 0) < 60:
                    continue

                watch = DEFAULT_WATCHLIST
                ex = user.get("exchange", DEFAULT_EXCHANGE)

                for sym in watch:
                    if sym == "XAUUSD":
                        continue
                    try:
                        df = fetch_ohlcv(sym, ex, timeframe="15m", limit=220)
                        live = fetch_live_price(sym, ex)
                        sig = build_signal(df)
                        inside = (sig.entry[0] <= live <= sig.entry[1])

                        if sig.side in ["BUY", "SELL"] and sig.confidence >= 70 and inside:
                            user["last_signal_ts"] = time.time()
                            text = "🚨 Auto فرصة قوية\n\n" + format_signal(sym, live, sig)
                            await app.bot.send_message(chat_id=chat_id, text=text)

                            # paper or real
                            qty = calc_position_size(user["capital"], user["risk_pct"], live, sig.sl)
                            if user["auto_on"]:
                                res = await place_order_real(user, sym, sig.side, qty)
                                await app.bot.send_message(chat_id=chat_id, text=res)
                            else:
                                await app.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"🧾 PAPER EXECUTED: {sig.side} {sym} qty={qty:.6f}",
                                )
                            break
                    except:
                        continue
        except:
            pass

        await asyncio.sleep(10)

# =========================
# Main
# =========================
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Start background auto loop
    app.create_task(auto_loop(app))

    # IMPORTANT: avoid Conflict (only one instance) + drop pending updates
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
