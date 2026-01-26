# bot.py
# Professional Multi-Exchange Trading Assistant Bot (Crypto) - PTB v21.6 + CCXT
# Features: Live prices, analysis, signals, chart images, scan opportunities, settings
# NOTE: This bot provides educational analysis, NOT financial advice.

import os
import re
import math
import time
import json
import asyncio
import logging
from datetime import datetime, timezone

import ccxt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ---------------------------
# CONFIG
# ---------------------------
import os
import time

TELEGRAM_TOKEN = None

for _ in range(5):  # نحاولو 5 مرات
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if TELEGRAM_TOKEN:
        TELEGRAM_TOKEN = TELEGRAM_TOKEN.strip()
        break
    time.sleep(1)

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ TELEGRAM_TOKEN غير موجود في ENV (Railway delay)")

# Default settings per user
DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "bybit").strip().lower()
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1h").strip()
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "200"))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ar").strip().lower()

# Rate limits / scan
SCAN_TOP = int(os.getenv("SCAN_TOP", "15"))  # number of symbols to scan
SCAN_TIMEFRAME = os.getenv("SCAN_TIMEFRAME", "1h").strip()
SCAN_LIMIT = int(os.getenv("SCAN_LIMIT", "200"))

# ---------------------------
# SUPPORTED EXCHANGES (CCXT)
# ---------------------------
SUPPORTED_EXCHANGES = {
    "binance": ccxt.binance,
    "bybit": ccxt.bybit,
    "okx": ccxt.okx,
    "kucoin": ccxt.kucoin,
}

# ---------------------------
# UI (Arabic)
# ---------------------------
TXT = {
    "ar": {
        "welcome": "🤖 *Smart Trading Bot*\n\nاختر من الأزرار 👇",
        "disclaimer": "⚠️ تنبيه: هذا محتوى تعليمي وليس نصيحة مالية.",
        "ask_symbol": "✍️ أرسل الرمز الآن مثل:\nBTC/USDT أو ETH/USDT",
        "bad_symbol": "❌ صيغة الرمز غير صحيحة. مثال صحيح: BTC/USDT",
        "set_ok": "✅ تم الحفظ.",
        "choose_exchange": "🏦 اختر منصة (Exchange):",
        "choose_tf": "⏱ اختر الفريم (Timeframe):",
        "settings": "⚙️ الإعدادات الحالية:\n- Exchange: {ex}\n- Timeframe: {tf}\n- Symbol: {sym}",
        "no_data": "❌ لم أستطع جلب البيانات الآن. جرّب Exchange آخر أو Symbol آخر.",
        "analysis_title": "📊 *تحليل {sym}* على {ex} ({tf})",
        "signal_title": "🎯 *إشارة {sym}* على {ex} ({tf})",
        "scan_title": "🔎 *Scan فرص اليوم* ({ex} / {tf})",
        "chart_caption": "📈 {sym} - Chart",
        "pick_from_buttons": "👇 اختار زر من القائمة.",
        "ai_disabled": "🧠 وضع الذكاء الاصطناعي غير مفعّل حالياً (سنضيفه في رقم 2).",
    }
}

# ---------------------------
# KEYBOARD
# ---------------------------
def main_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton("📊 تحليل", callback_data="menu:analysis"),
            InlineKeyboardButton("🎯 إشارة", callback_data="menu:signal"),
        ],
        [
            InlineKeyboardButton("🔎 Scan", callback_data="menu:scan"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton("🧠 Chat", callback_data="menu:chat"),
        ],
    ]
    return InlineKeyboardMarkup(kb)

def exchange_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton("Bybit", callback_data="setex:bybit"),
            InlineKeyboardButton("OKX", callback_data="setex:okx"),
        ],
        [
            InlineKeyboardButton("KuCoin", callback_data="setex:kucoin"),
            InlineKeyboardButton("Binance", callback_data="setex:binance"),
        ],
        [
            InlineKeyboardButton("⬅️ رجوع", callback_data="menu:home")
        ]
    ]
    return InlineKeyboardMarkup(kb)

def timeframe_keyboard() -> InlineKeyboardMarkup:
    tfs = ["15m", "1h", "4h", "1d"]
    kb = [[InlineKeyboardButton(tf, callback_data=f"settf:{tf}") for tf in tfs[:2]],
          [InlineKeyboardButton(tf, callback_data=f"settf:{tf}") for tf in tfs[2:]],
          [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:settings")]]
    return InlineKeyboardMarkup(kb)

# ---------------------------
# HELPERS
# ---------------------------
def lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", DEFAULT_LANGUAGE) or "ar"

def t(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
    l = lang(context)
    s = TXT.get(l, TXT["ar"]).get(key, key)
    return s.format(**kwargs)

def normalize_symbol(text: str) -> str:
    # Accept: BTC, BTCUSDT, BTC/USDT, btc/usdt
    x = text.strip().upper().replace(" ", "")
    if "/" in x:
        base, quote = x.split("/", 1)
        if base and quote:
            return f"{base}/{quote}"
        return ""
    # If someone sends BTC -> default quote USDT
    if re.fullmatch(r"[A-Z]{2,10}", x):
        return f"{x}/USDT"
    # If BTCUSDT
    m = re.fullmatch(r"([A-Z]{2,10})(USDT|USD|USDC|BUSD)", x)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return ""

def get_exchange(name: str):
    name = (name or DEFAULT_EXCHANGE).lower()
    if name not in SUPPORTED_EXCHANGES:
        name = "bybit"
    ex = SUPPORTED_EXCHANGES[name]({"enableRateLimit": True})
    return ex, name

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

def now_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ---------------------------
# DATA + INDICATORS
# ---------------------------
def fetch_ohlcv(symbol: str, ex_name: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    ex, ex_name = get_exchange(ex_name)
    try:
        ex.load_markets()
        if symbol not in ex.markets:
            # Try to find close match
            # Sometimes exchange uses :USDT for perpetual; we keep spot symbols only for now
            return None
        ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not ohlcv or len(ohlcv) < 50:
            return None
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df.set_index("ts", inplace=True)
        return df
    except Exception as e:
        log.exception("fetch_ohlcv error: %s", e)
        return None

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # EMA
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()

    # RSI(14)
    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / (loss.replace(0, np.nan))
    out["rsi14"] = 100 - (100 / (1 + rs))
    out["rsi14"] = out["rsi14"].fillna(method="bfill").fillna(50)

    # ATR(14)
    high_low = out["high"] - out["low"]
    high_close = (out["high"] - out["close"].shift()).abs()
    low_close = (out["low"] - out["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    out["atr14"] = tr.rolling(14).mean().fillna(method="bfill")

    return out

def support_resistance(df: pd.DataFrame, lookback: int = 60):
    # simple: recent swing high/low
    x = df.tail(lookback)
    sup = float(x["low"].min())
    res = float(x["high"].max())
    return sup, res

def generate_signal(df: pd.DataFrame):
    # Returns dict: direction, entry, sl, tp1, tp2, confidence, reasoning
    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(last["close"])
    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    rsi = float(last["rsi14"])
    atr = float(last["atr14"])

    sup, res = support_resistance(df, lookback=80)

    trend_up = ema20 > ema50 and price > ema20
    trend_down = ema20 < ema50 and price < ema20

    # Momentum
    rsi_overbought = rsi >= 70
    rsi_oversold = rsi <= 30

    # Decide
    direction = "WAIT"
    confidence = 50
    reasons = []

    if trend_up and not rsi_overbought:
        direction = "LONG"
        confidence = 65
        reasons.append("الاتجاه صاعد (EMA20 فوق EMA50 والسعر فوق EMA20).")
        if rsi < 60:
            confidence += 5
            reasons.append("RSI معتدل (ليس تشبع شراء).")
    elif trend_down and not rsi_oversold:
        direction = "SHORT"
        confidence = 65
        reasons.append("الاتجاه هابط (EMA20 تحت EMA50 والسعر تحت EMA20).")
        if rsi > 40:
            confidence += 5
            reasons.append("RSI معتدل (ليس تشبع بيع).")
    else:
        reasons.append("السوق غير واضح أو في منطقة تشبع.")

    # Risk plan (no leverage)
    # Entry near price, SL based on ATR, TP based on RR
    rr = 2.0  # 1:2
    if direction == "LONG":
        entry = price
        sl = max(price - 1.5 * atr, sup * 0.995)
        tp1 = entry + (entry - sl) * rr
        tp2 = min(res * 0.995, entry + (entry - sl) * (rr + 0.8))
        reasons.append(f"دعم قريب: {sup:.4g} | مقاومة: {res:.4g}")
    elif direction == "SHORT":
        entry = price
        sl = min(price + 1.5 * atr, res * 1.005)
        tp1 = entry - (sl - entry) * rr
        tp2 = max(sup * 1.005, entry - (sl - entry) * (rr + 0.8))
        reasons.append(f"دعم قريب: {sup:.4g} | مقاومة: {res:.4g}")
    else:
        entry = price
        sl = None
        tp1 = None
        tp2 = None

    # Clamp confidence
    confidence = int(max(0, min(95, confidence)))

    return {
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "confidence": confidence,
        "rsi": rsi,
        "ema20": ema20,
        "ema50": ema50,
        "atr": atr,
        "support": sup,
        "resistance": res,
        "reasons": reasons,
    }

# ---------------------------
# CHART IMAGE
# ---------------------------
def generate_chart_png(df: pd.DataFrame, symbol: str, ex_name: str, timeframe: str) -> str | None:
    try:
        tail = df.tail(120).copy()
        # Build simple candlestick-like plot using lines (no mplfinance dependency)
        fig = plt.figure(figsize=(10, 5))
        ax = fig.add_subplot(1, 1, 1)

        x = np.arange(len(tail))
        o = tail["open"].values
        h = tail["high"].values
        l = tail["low"].values
        c = tail["close"].values

        # wick
        for i in range(len(tail)):
            ax.vlines(x[i], l[i], h[i], linewidth=1)

        # body
        for i in range(len(tail)):
            y0 = min(o[i], c[i])
            y1 = max(o[i], c[i])
            ax.vlines(x[i], y0, y1, linewidth=4)

        ax.plot(x, tail["ema20"].values, linewidth=1.5, label="EMA20")
        ax.plot(x, tail["ema50"].values, linewidth=1.5, label="EMA50")

        ax.set_title(f"{symbol} | {ex_name.upper()} | {timeframe}")
        ax.set_xlim(0, len(tail) - 1)
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.2)

        # Save
        out_path = f"/tmp/chart_{symbol.replace('/', '')}_{ex_name}_{timeframe}.png"
        plt.tight_layout()
        plt.savefig(out_path, dpi=160)
        plt.close(fig)
        return out_path
    except Exception as e:
        log.exception("generate_chart_png error: %s", e)
        return None

# ---------------------------
# FORMATTERS
# ---------------------------
def fmt_price(x):
    if x is None:
        return "-"
    if x >= 1000:
        return f"{x:,.2f}"
    if x >= 1:
        return f"{x:.4f}"
    return f"{x:.8f}"

def format_analysis(symbol: str, ex: str, tf: str, sig: dict) -> str:
    direction = sig["direction"]
    conf = sig["confidence"]
    rsi = sig["rsi"]
    ema20 = sig["ema20"]
    ema50 = sig["ema50"]
    sup = sig["support"]
    res = sig["resistance"]
    entry = sig["entry"]
    atr = sig["atr"]

    lines = []
    lines.append(f"{direction} | ثقة: {conf}%")
    lines.append(f"السعر الحالي: {fmt_price(entry)}")
    lines.append(f"RSI(14): {rsi:.1f}")
    lines.append(f"EMA20: {fmt_price(ema20)} | EMA50: {fmt_price(ema50)}")
    lines.append(f"Support: {fmt_price(sup)} | Resistance: {fmt_price(res)}")
    lines.append(f"ATR(14): {fmt_price(atr)}")
    lines.append("")
    lines.append("🧠 السبب:")
    for r in sig["reasons"][:6]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("⚠️ هذا محتوى تعليمي وليس نصيحة مالية.")
    lines.append(f"🕒 {now_utc_str()}")
    return "\n".join(lines)

def format_signal(symbol: str, ex: str, tf: str, sig: dict) -> str:
    direction = sig["direction"]
    conf = sig["confidence"]
    entry = sig["entry"]
    sl = sig["sl"]
    tp1 = sig["tp1"]
    tp2 = sig["tp2"]

    if direction == "WAIT":
        return (
            f"🎯 إشارة {symbol} ({ex.upper()} / {tf})\n\n"
            f"الاتجاه الآن: WAIT (لا توجد فرصة واضحة)\n"
            f"السعر: {fmt_price(entry)}\n\n"
            f"⚠️ هذا محتوى تعليمي وليس نصيحة مالية.\n"
            f"🕒 {now_utc_str()}"
        )

    # RR
    rr = "-"
    if sl and tp1:
        if direction == "LONG":
            rr = (tp1 - entry) / (entry - sl + 1e-9)
        else:
            rr = (entry - tp1) / (sl - entry + 1e-9)

    return (
        f"🎯 إشارة {symbol} ({ex.upper()} / {tf})\n\n"
        f"📌 الاتجاه: {direction} | ثقة: {conf}%\n"
        f"🟢 Entry: {fmt_price(entry)}\n"
        f"🔴 SL: {fmt_price(sl)}\n"
        f"🎯 TP1: {fmt_price(tp1)}\n"
        f"🎯 TP2: {fmt_price(tp2)}\n"
        f"📏 RR تقريبي: {rr if isinstance(rr, str) else f'{rr:.2f}'}\n\n"
        f"💡 إدارة المخاطر: لا تخاطر بأكثر من 1% - 2% من رأس المال.\n"
        f"⚠️ هذا محتوى تعليمي وليس نصيحة مالية.\n"
        f"🕒 {now_utc_str()}"
    )

# ---------------------------
# SCAN (Top Opportunities)
# ---------------------------
def scan_opportunities(ex_name: str, tf: str) -> list[dict]:
    ex, ex_name = get_exchange(ex_name)
    ex.load_markets()
    # Keep USDT pairs only, spot
    symbols = [s for s in ex.symbols if s.endswith("/USDT")]
    # Take a subset to avoid heavy load
    symbols = symbols[: max(SCAN_TOP, 10)]

    results = []
    for sym in symbols:
        df = fetch_ohlcv(sym, ex_name, tf, SCAN_LIMIT)
        if df is None:
            continue
        df = compute_indicators(df)
        sig = generate_signal(df)
        if sig["direction"] in ("LONG", "SHORT") and sig["confidence"] >= 65:
            results.append({
                "symbol": sym,
                "direction": sig["direction"],
                "confidence": sig["confidence"],
                "price": sig["entry"],
                "rsi": sig["rsi"],
            })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results[:10]

# ---------------------------
# HANDLERS
# ---------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("exchange", DEFAULT_EXCHANGE)
    context.user_data.setdefault("timeframe", DEFAULT_TIMEFRAME)
    context.user_data.setdefault("symbol", "BTC/USDT")
    context.user_data.setdefault("mode", "home")
    await update.message.reply_text(
        t(context, "welcome"),
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📌 أوامر:\n"
        "/start\n"
        "/set_symbol BTC/USDT\n"
        "/set_exchange bybit|okx|kucoin|binance\n"
        "/set_tf 15m|1h|4h|1d\n"
    )
    await update.message.reply_text(msg)

async def cmd_set_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(context, "ask_symbol"))
        return
    sym = normalize_symbol(" ".join(context.args))
    if not sym:
        await update.message.reply_text(t(context, "bad_symbol"))
        return
    context.user_data["symbol"] = sym
    await update.message.reply_text(f"✅ Symbol = {sym}")

async def cmd_set_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(context, "choose_exchange"), reply_markup=exchange_keyboard())
        return
    ex = context.args[0].strip().lower()
    if ex not in SUPPORTED_EXCHANGES:
        await update.message.reply_text("❌ Exchange غير مدعوم. جرّب: bybit / okx / kucoin / binance")
        return
    context.user_data["exchange"] = ex
    await update.message.reply_text(f"✅ Exchange = {ex}")

async def cmd_set_tf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(context, "choose_tf"), reply_markup=timeframe_keyboard())
        return
    tf = context.args[0].strip()
    if tf not in ("15m", "1h", "4h", "1d"):
        await update.message.reply_text("❌ Timeframe غير مدعوم. جرّب: 15m / 1h / 4h / 1d")
        return
    context.user_data["timeframe"] = tf
    await update.message.reply_text(f"✅ Timeframe = {tf}")

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    # Menu routing
    if data.startswith("menu:"):
        page = data.split(":", 1)[1]
        context.user_data["mode"] = page

        if page == "home":
            await query.edit_message_text(t(context, "welcome"), reply_markup=main_keyboard(), parse_mode="Markdown")
            return

        if page == "analysis":
            await query.edit_message_text(t(context, "ask_symbol"), reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:home")]
            ]))
            return

        if page == "signal":
            await query.edit_message_text(t(context, "ask_symbol"), reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:home")]
            ]))
            return

        if page == "scan":
            ex = context.user_data.get("exchange", DEFAULT_EXCHANGE)
            tf = context.user_data.get("timeframe", DEFAULT_TIMEFRAME)
            await query.edit_message_text("⏳ جاري البحث عن أفضل الفرص...")
            # run sync scan in thread
            results = await asyncio.to_thread(scan_opportunities, ex, SCAN_TIMEFRAME)

            if not results:
                await query.edit_message_text(
                    f"{t(context, 'scan_title', ex=ex, tf=SCAN_TIMEFRAME)}\n\nلا توجد فرص قوية الآن.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="menu:home")]]),
                    parse_mode="Markdown",
                )
                return

            lines = [t(context, "scan_title", ex=ex, tf=SCAN_TIMEFRAME), ""]
            for r in results:
                lines.append(f"- {r['symbol']} | {r['direction']} | ثقة {r['confidence']}% | سعر {fmt_price(r['price'])} | RSI {r['rsi']:.0f}")
            lines.append("")
            lines.append(TXT["ar"]["disclaimer"])

            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="menu:home")]]),
            )
            return

        if page == "settings":
            ex = context.user_data.get("exchange", DEFAULT_EXCHANGE)
            tf = context.user_data.get("timeframe", DEFAULT_TIMEFRAME)
            sym = context.user_data.get("symbol", "BTC/USDT")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏦 Exchange", callback_data="menu:exchange"),
                 InlineKeyboardButton("⏱ Timeframe", callback_data="menu:timeframe")],
                [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:home")],
            ])
            await query.edit_message_text(t(context, "settings", ex=ex, tf=tf, sym=sym), reply_markup=kb)
            return

        if page == "exchange":
            await query.edit_message_text(t(context, "choose_exchange"), reply_markup=exchange_keyboard())
            return

        if page == "timeframe":
            await query.edit_message_text(t(context, "choose_tf"), reply_markup=timeframe_keyboard())
            return

        if page == "chat":
            await query.edit_message_text(
                t(context, "ai_disabled"),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="menu:home")]]),
            )
            return

    # Settings actions
    if data.startswith("setex:"):
        ex = data.split(":", 1)[1].lower()
        if ex in SUPPORTED_EXCHANGES:
            context.user_data["exchange"] = ex
            await query.edit_message_text(f"✅ Exchange = {ex}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:settings")]
            ]))
        else:
            await query.edit_message_text("❌ Exchange غير مدعوم.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:settings")]
            ]))
        return

    if data.startswith("settf:"):
        tf = data.split(":", 1)[1]
        if tf in ("15m", "1h", "4h", "1d"):
            context.user_data["timeframe"] = tf
            await query.edit_message_text(f"✅ Timeframe = {tf}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:settings")]
            ]))
        else:
            await query.edit_message_text("❌ Timeframe غير مدعوم.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="menu:settings")]
            ]))
        return

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    mode = context.user_data.get("mode", "home")

    # If user typed symbol anytime
    sym = normalize_symbol(text)
    if sym:
        context.user_data["symbol"] = sym

        ex = context.user_data.get("exchange", DEFAULT_EXCHANGE)
        tf = context.user_data.get("timeframe", DEFAULT_TIMEFRAME)

        # Fetch data
        await update.message.reply_text("⏳ جاري جلب البيانات...")
        df = await asyncio.to_thread(fetch_ohlcv, sym, ex, tf, DEFAULT_LIMIT)
        if df is None:
            await update.message.reply_text(t(context, "no_data"), reply_markup=main_keyboard())
            return
        df = await asyncio.to_thread(compute_indicators, df)
        sig = await asyncio.to_thread(generate_signal, df)

        # Chart
        chart_path = await asyncio.to_thread(generate_chart_png, df, sym, ex, tf)

        if mode == "signal":
            msg = t(context, "signal_title", sym=sym, ex=ex, tf=tf) + "\n\n" + format_signal(sym, ex, tf, sig)
        else:
            # default analysis
            msg = t(context, "analysis_title", sym=sym, ex=ex, tf=tf) + "\n\n" + format_analysis(sym, ex, tf, sig)

        await update.message.reply_text(msg, reply_markup=main_keyboard(), parse_mode="Markdown")

        if chart_path and os.path.exists(chart_path):
            try:
                with open(chart_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption=t(context, "chart_caption", sym=sym))
            except Exception:
                pass
        return

    # If not symbol: gently guide
    await update.message.reply_text(t(context, "pick_from_buttons"), reply_markup=main_keyboard())

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled error: %s", context.error)

# ---------------------------
# MAIN
# ---------------------------
def build_app():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("set_symbol", cmd_set_symbol))
    app.add_handler(CommandHandler("set_exchange", cmd_set_exchange))
    app.add_handler(CommandHandler("set_tf", cmd_set_tf))

    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.add_error_handler(on_error)
    return app

def main():
    app = build_app()
    log.info("Bot started.")
    # run_polling handles event loop properly (prevents 'no running event loop')
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
