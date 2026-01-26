# bot.py
# Smart Trading Bot (Crypto + Stocks/Gold via optional API) + Signals + Charts + Auto Paper + Optional Live Trading + Optional AI
# python-telegram-bot[job-queue]==21.6

import os
import io
import math
import time
import json
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from dotenv import load_dotenv

import ccxt

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Optional OpenAI (AI explanations/chat)
OPENAI_AVAILABLE = True
try:
    from openai import OpenAI
except Exception:
    OPENAI_AVAILABLE = False

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("smartbot")

# -----------------------------
# ENV
# -----------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5").strip()

# Crypto (ccxt)
CRYPTO_EXCHANGE_ID = os.getenv("CRYPTO_EXCHANGE_ID", "binance").strip().lower()  # binance by default

# Live trading keys (optional)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip()

# Stocks/Gold/Forex via TwelveData (optional)
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()

# Auto loop
AUTO_INTERVAL_SEC = int(os.getenv("AUTO_INTERVAL_SEC", "300"))  # 5 minutes default
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "15m").strip()  # for crypto

# Safety defaults
DEFAULT_RISK_PCT = float(os.getenv("DEFAULT_RISK_PCT", "1.0"))  # % per trade


# -----------------------------
# UI / States
# -----------------------------
MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📊 تحليل"), KeyboardButton("🎯 إشارة")],
        [KeyboardButton("🤖 Auto Paper"), KeyboardButton("⚡ Auto Live")],
        [KeyboardButton("🧠 دردشة"), KeyboardButton("⚙️ إعدادات")],
        [KeyboardButton("🧾 Scan"), KeyboardButton("🐋 Whales")],
    ],
    resize_keyboard=True,
)

STATE_KEY = "state"
STATE_NONE = "none"
STATE_WAIT_SYMBOL_ANALYSIS = "wait_symbol_analysis"
STATE_WAIT_SYMBOL_SIGNAL = "wait_symbol_signal"
STATE_WAIT_SYMBOL_SCAN = "wait_symbol_scan"
STATE_WAIT_CHAT = "wait_chat"
STATE_WAIT_CAPITAL = "wait_capital"

# Per-user keys saved in user_data
UD_SYMBOL = "symbol"
UD_MARKET = "market"  # "crypto" or "twelvedata"
UD_CAPITAL = "capital"
UD_RISK = "risk_pct"
UD_AI = "ai_enabled"
UD_AUTO_PAPER = "auto_paper_on"
UD_AUTO_LIVE = "auto_live_on"
UD_POSITIONS = "paper_positions"  # dict symbol-> position
UD_CONFIRM_LIVE = "confirm_live"  # step confirmation


# -----------------------------
# Helpers
# -----------------------------
def is_crypto_symbol(sym: str) -> bool:
    # Accept BTC, ETH, SOL, etc. And BTCUSDT / BTC/USDT
    s = sym.upper().replace(" ", "")
    if "/" in s:
        base, quote = s.split("/", 1)
        return base.isalnum() and quote.isalnum()
    if s.endswith("USDT") and len(s) >= 6:
        return True
    # plain BTC/ETH -> treat as crypto base with USDT
    return s.isalpha() and 2 <= len(s) <= 10


def normalize_crypto_symbol(sym: str) -> str:
    s = sym.upper().replace(" ", "")
    if "/" in s:
        return s
    if s.endswith("USDT") and len(s) >= 6:
        base = s[:-4]
        return f"{base}/USDT"
    # BTC -> BTC/USDT
    return f"{s}/USDT"


def human_money(x: float) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "-"
    if abs(x) >= 1000:
        return f"{x:,.2f}"
    return f"{x:.4f}".rstrip("0").rstrip(".")


def safe_float(text: str) -> Optional[float]:
    try:
        t = text.replace(",", ".").strip()
        return float(t)
    except Exception:
        return None


def now_ts() -> int:
    return int(time.time())


# -----------------------------
# Market Data Providers
# -----------------------------
class CryptoData:
    def __init__(self):
        if CRYPTO_EXCHANGE_ID not in ccxt.exchanges:
            raise ValueError(f"Unsupported exchange id: {CRYPTO_EXCHANGE_ID}")
        ex_class = getattr(ccxt, CRYPTO_EXCHANGE_ID)
        self.ex = ex_class({"enableRateLimit": True})

    def fetch_ohlcv(self, symbol: str, timeframe: str = DEFAULT_TIMEFRAME, limit: int = 200) -> pd.DataFrame:
        ohlcv = self.ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df

    def fetch_last_price(self, symbol: str) -> float:
        t = self.ex.fetch_ticker(symbol)
        return float(t["last"]) if t.get("last") is not None else float(t["close"])


async def http_get_json(url: str, timeout: int = 15) -> Dict[str, Any]:
    # lightweight HTTP using aiohttp if available; fallback to urllib
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as resp:
                return await resp.json()
    except Exception:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw)


class TwelveData:
    """
    Optional provider for stocks/forex/gold via TWELVEDATA_API_KEY.
    You can use symbols like: TSLA, AAPL, XAU/USD, EUR/USD
    Docs are on TwelveData website (user supplies key).
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def normalize_symbol(sym: str) -> str:
        s = sym.upper().strip().replace(" ", "")
        # allow XAUUSD -> XAU/USD for TwelveData
        if s == "XAUUSD":
            return "XAU/USD"
        if len(s) == 6 and s.isalpha():  # EURUSD -> EUR/USD
            return f"{s[:3]}/{s[3:]}"
        return s

    async def fetch_last_price(self, symbol: str) -> Tuple[Optional[float], Optional[str]]:
        s = self.normalize_symbol(symbol)
        url = f"https://api.twelvedata.com/price?symbol={s}&apikey={self.api_key}"
        data = await http_get_json(url)
        if "price" in data:
            return float(data["price"]), s
        return None, data.get("message", "No price")

    async def fetch_ohlcv(self, symbol: str, interval: str = "15min", outputsize: int = 200) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        s = self.normalize_symbol(symbol)
        url = (
            f"https://api.twelvedata.com/time_series?"
            f"symbol={s}&interval={interval}&outputsize={outputsize}&apikey={self.api_key}"
            f"&format=JSON"
        )
        data = await http_get_json(url)
        if "values" not in data:
            return None, data.get("message", "No data")
        vals = data["values"]
        df = pd.DataFrame(vals)
        # TwelveData returns strings
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime")
        df.rename(columns={"datetime": "ts"}, inplace=True)
        for c in ["open", "high", "low", "close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = np.nan
        return df[["ts", "open", "high", "low", "close", "volume"]], None


# -----------------------------
# Indicators / Strategy
# -----------------------------
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1 / period, adjust=False).mean()
    ma_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = ma_up / (ma_down + 1e-12)
    return 100 - (100 / (1 + rs))


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat(
        [
            (high - low),
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


@dataclass
class Signal:
    side: str  # "BUY" or "SELL" or "NONE"
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr: float
    confidence: int
    reason: str


def generate_signal_from_df(df: pd.DataFrame) -> Signal:
    # Basic robust signal: trend (EMA20/EMA50), momentum (RSI), volatility (ATR)
    c = df["close"]
    df = df.copy()
    df["ema20"] = ema(c, 20)
    df["ema50"] = ema(c, 50)
    df["rsi14"] = rsi(c, 14)
    df["atr14"] = atr(df, 14)

    last = df.iloc[-1]
    entry = float(last["close"])
    a = float(last["atr14"]) if not math.isnan(float(last["atr14"])) else max(entry * 0.005, 1e-6)

    trend_up = last["ema20"] > last["ema50"]
    trend_down = last["ema20"] < last["ema50"]
    r = float(last["rsi14"])

    # Confidence heuristic
    conf = 50
    if trend_up:
        conf += 15
    if trend_down:
        conf += 15
    if r >= 55:
        conf += 10
    if r <= 45:
        conf += 10
    conf = int(max(0, min(95, conf)))

    # Decision
    side = "NONE"
    reason_parts = []
    if trend_up and r >= 52:
        side = "BUY"
        reason_parts.append("الاتجاه صاعد (EMA20 فوق EMA50)")
        reason_parts.append(f"الزخم إيجابي (RSI={r:.1f})")
    elif trend_down and r <= 48:
        side = "SELL"
        reason_parts.append("الاتجاه هابط (EMA20 تحت EMA50)")
        reason_parts.append(f"الزخم سلبي (RSI={r:.1f})")
    else:
        reason_parts.append(f"سوق متذبذب/غير واضح (RSI={r:.1f})")
        return Signal("NONE", entry, entry, entry, entry, 0.0, conf, " | ".join(reason_parts))

    # Risk model (ATR based)
    if side == "BUY":
        sl = entry - 1.6 * a
        tp1 = entry + 1.6 * a
        tp2 = entry + 2.6 * a
        rr = (tp1 - entry) / max(entry - sl, 1e-9)
    else:
        sl = entry + 1.6 * a
        tp1 = entry - 1.6 * a
        tp2 = entry - 2.6 * a
        rr = (entry - tp1) / max(sl - entry, 1e-9)

    reason_parts.append(f"تقلب (ATR)={a:.4f}")
    return Signal(side, entry, sl, tp1, tp2, float(rr), conf, " | ".join(reason_parts))


def position_size(capital: float, risk_pct: float, entry: float, sl: float) -> Tuple[float, float]:
    # returns (risk_amount, qty)
    risk_amount = capital * (risk_pct / 100.0)
    per_unit_risk = abs(entry - sl)
    if per_unit_risk <= 0:
        return risk_amount, 0.0
    qty = risk_amount / per_unit_risk
    return risk_amount, qty


# -----------------------------
# Chart
# -----------------------------
def make_chart(df: pd.DataFrame, title: str) -> bytes:
    df = df.copy()
    df = df.tail(120)
    x = df["ts"]
    c = df["close"]
    e20 = ema(c, 20)
    e50 = ema(c, 50)

    plt.figure(figsize=(10, 5))
    plt.plot(x, c, label="Close")
    plt.plot(x, e20, label="EMA20")
    plt.plot(x, e50, label="EMA50")
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160)
    plt.close()
    buf.seek(0)
    return buf.read()


# -----------------------------
# Optional AI
# -----------------------------
def ai_client() -> Optional["OpenAI"]:
    if not OPENAI_AVAILABLE:
        return None
    if not OPENAI_API_KEY:
        return None
    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        return None


async def ai_explain(symbol: str, signal: Signal, last_price: float, extra: str = "") -> Optional[str]:
    client = ai_client()
    if client is None:
        return None
    prompt = f"""
أنت محلل أسواق محترف. اكتب شرحاً عملياً وقصيراً (عربي تونسي/فصحى بسيط) للإشارة التالية بدون مبالغة.
الرمز: {symbol}
السعر الحالي: {last_price}
الإشارة: {signal.side}
Entry: {signal.entry}
SL: {signal.sl}
TP1: {signal.tp1}
TP2: {signal.tp2}
RR: {signal.rr:.2f}
Confidence: {signal.confidence}/100
الأسباب: {signal.reason}
{extra}

طلبي:
- أعطني "خطة تنفيذ" واضحة: أين ندخل، أين نخرج، ومتى نلغي الفكرة
- أعطني تحذير مخاطر محترم
- لا تعطي وعود ربح
"""
    try:
        # Official python usage uses Responses API 1
        resp = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
        )
        return getattr(resp, "output_text", None) or None
    except Exception as e:
        log.warning("AI error: %s", e)
        return None


# -----------------------------
# Live Trading (optional)
# -----------------------------
class LiveTrader:
    def __init__(self):
        self.enabled = bool(BINANCE_API_KEY and BINANCE_API_SECRET)
        self.ex = ccxt.binance({
            "apiKey": BINANCE_API_KEY,
            "secret": BINANCE_API_SECRET,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })

    def can_trade(self) -> bool:
        return self.enabled

    def market_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        # Spot market order only. No leverage.
        if side == "BUY":
            return self.ex.create_market_buy_order(symbol, amount)
        else:
            return self.ex.create_market_sell_order(symbol, amount)


# -----------------------------
# Telegram Handlers
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault(STATE_KEY, STATE_NONE)
    context.user_data.setdefault(UD_RISK, DEFAULT_RISK_PCT)
    context.user_data.setdefault(UD_AI, True)  # AI is optional, will fallback if no key
    context.user_data.setdefault(UD_AUTO_PAPER, False)
    context.user_data.setdefault(UD_AUTO_LIVE, False)
    context.user_data.setdefault(UD_POSITIONS, {})
    context.user_data.setdefault(UD_CONFIRM_LIVE, 0)

    text = (
        "🤖 *Smart Trading Bot*\n\n"
        "اختر من الأزرار:\n"
        "📊 تحليل = تحليل + شارت\n"
        "🎯 إشارة = Entry/SL/TP + خطة\n"
        "🤖 Auto Paper = محاكاة تلقائية\n"
        "⚡ Auto Live = تداول حقيقي (اختياري + مفاتيح منصة)\n"
        "🧠 دردشة = ذكاء اصطناعي (اختياري)\n\n"
        "ملاحظة: *لا رافعة* افتراضياً، والتداول الحقيقي OFF حتى تأكد.\n"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KB, parse_mode=ParseMode.MARKDOWN)


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    risk = context.user_data.get(UD_RISK, DEFAULT_RISK_PCT)
    ai_on = context.user_data.get(UD_AI, True)
    paper_on = context.user_data.get(UD_AUTO_PAPER, False)
    live_on = context.user_data.get(UD_AUTO_LIVE, False)

    td = "✅" if TWELVEDATA_API_KEY else "❌"
    ai = "✅" if (OPENAI_API_KEY and OPENAI_AVAILABLE) else "❌"
    bn = "✅" if (BINANCE_API_KEY and BINANCE_API_SECRET) else "❌"

    msg = (
        "⚙️ *الإعدادات*\n\n"
        f"- Risk per trade: *{risk}%*\n"
        f"- AI Enabled: *{ai_on}* (OpenAI key: {ai})\n"
        f"- TwelveData key (Stocks/Gold): {td}\n"
        f"- Binance keys (Live Trading): {bn}\n"
        f"- Auto Paper: *{paper_on}*\n"
        f"- Auto Live: *{live_on}*\n\n"
        "أوامر مفيدة:\n"
        "`/risk 1.0`  (مثال)\n"
        "`/capital 1000`\n"
        "`/ai on` أو `/ai off`\n"
        "`/auto_paper on` أو `/auto_paper off`\n"
        "`/auto_live on` أو `/auto_live off`\n"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب: /risk 1.0")
        return
    val = safe_float(context.args[0])
    if val is None or val <= 0 or val > 10:
        await update.message.reply_text("حط رقم بين 0.1 و 10")
        return
    context.user_data[UD_RISK] = float(val)
    await update.message.reply_text(f"✅ تم: Risk = {val}%")


async def cmd_capital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب: /capital 1000")
        return
    val = safe_float(context.args[0])
    if val is None or val <= 0:
        await update.message.reply_text("حط رقم صحيح > 0")
        return
    context.user_data[UD_CAPITAL] = float(val)
    await update.message.reply_text(f"✅ تم حفظ رأس المال: {val}")


async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب: /ai on أو /ai off")
        return
    v = context.args[0].lower()
    if v in ("on", "yes", "1", "true"):
        context.user_data[UD_AI] = True
        await update.message.reply_text("✅ AI ON (إذا المفتاح موجود)")
    elif v in ("off", "no", "0", "false"):
        context.user_data[UD_AI] = False
        await update.message.reply_text("✅ AI OFF")
    else:
        await update.message.reply_text("اكتب: /ai on أو /ai off")


async def cmd_auto_paper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب: /auto_paper on أو /auto_paper off")
        return
    v = context.args[0].lower()
    if v in ("on", "1", "true", "yes"):
        context.user_data[UD_AUTO_PAPER] = True
        await update.message.reply_text("✅ Auto Paper ON")
    else:
        context.user_data[UD_AUTO_PAPER] = False
        await update.message.reply_text("✅ Auto Paper OFF")


async def cmd_auto_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب: /auto_live on أو /auto_live off")
        return
    v = context.args[0].lower()
    trader = LiveTrader()
    if v in ("on", "1", "true", "yes"):
        if not trader.can_trade():
            await update.message.reply_text("❌ ما فماش BINANCE_API_KEY و BINANCE_API_SECRET في ENV.")
            return
        # require 2-step confirmation
        context.user_data[UD_CONFIRM_LIVE] = 1
        await update.message.reply_text(
            "⚠️ *تداول حقيقي*.\n"
            "اكتب بالضبط: `CONFIRM LIVE`\n"
            "باش نفعّلو Auto Live.\n\n"
            "ملاحظة: بدون رافعة، Spot فقط.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        context.user_data[UD_AUTO_LIVE] = False
        context.user_data[UD_CONFIRM_LIVE] = 0
        await update.message.reply_text("✅ Auto Live OFF")


async def analysis_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE_KEY] = STATE_WAIT_SYMBOL_ANALYSIS
    await update.message.reply_text("📊 أرسل الرمز الآن (مثال: BTC أو BTCUSDT أو TSLA أو XAUUSD)")


async def signal_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE_KEY] = STATE_WAIT_SYMBOL_SIGNAL
    await update.message.reply_text("🎯 أرسل الرمز الآن (مثال: BTC أو BTCUSDT أو TSLA أو XAUUSD)")


async def chat_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE_KEY] = STATE_WAIT_CHAT
    await update.message.reply_text("🧠 اكتب سؤالك (سأرد AI إذا المفتاح موجود، وإلا رد عادي).")


async def whales_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐋 Whales: هذه ميزة تحتاج WhaleAlert API Key. (نزيدوها بعد)")


async def scan_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE_KEY] = STATE_WAIT_SYMBOL_SCAN
    await update.message.reply_text("🧾 Scan: أرسل رمز Crypto (مثال BTC) ونعطيك Quick Scan.")


async def auto_paper_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    on = context.user_data.get(UD_AUTO_PAPER, False)
    context.user_data[UD_AUTO_PAPER] = not on
    await update.message.reply_text(f"🤖 Auto Paper = {context.user_data[UD_AUTO_PAPER]}")


async def auto_live_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # guide user to /auto_live on flow
    await update.message.reply_text("⚡ لتفعيل Auto Live: اكتب /auto_live on (لازم مفاتيح Binance في ENV)")


# -----------------------------
# Core actions
# -----------------------------
async def get_market_df_and_price(symbol_raw: str) -> Tuple[str, str, Optional[pd.DataFrame], Optional[float], Optional[str]]:
    """
    returns: (market_type, normalized_symbol, df, last_price, error)
    market_type: crypto | twelvedata
    """
    sym = symbol_raw.strip()

    # Crypto path (default)
    if is_crypto_symbol(sym):
        try:
            crypto = CryptoData()
            symbol = normalize_crypto_symbol(sym)
            df = crypto.fetch_ohlcv(symbol, timeframe=DEFAULT_TIMEFRAME, limit=200)
            price = float(df["close"].iloc[-1])
            return "crypto", symbol, df, price, None
        except Exception as e:
            return "crypto", normalize_crypto_symbol(sym), None, None, f"خطأ Crypto data: {e}"

    # Non-crypto path via TwelveData
    if not TWELVEDATA_API_KEY:
        return "twelvedata", sym.upper(), None, None, "لا يوجد TWELVEDATA_API_KEY للأسهم/الذهب حالياً."
    td = TwelveData(TWELVEDATA_API_KEY)
    norm = td.normalize_symbol(sym)
    df, err = await td.fetch_ohlcv(norm, interval="15min", outputsize=200)
    if err:
        price, err2 = await td.fetch_last_price(norm)
        if price is not None:
            return "twelvedata", norm, None, price, None
        return "twelvedata", norm, None, None, err or err2
    price = float(df["close"].iloc[-1])
    return "twelvedata", norm, df, price, None


def format_signal_text(symbol: str, price: float, sig: Signal, capital: Optional[float], risk_pct: float) -> str:
    if sig.side == "NONE":
        return (
            f"🎯 *Signal* — {symbol}\n"
            f"السعر: *{human_money(price)}*\n\n"
            "❌ *لا توجد فرصة واضحة الآن* (سوق متذبذب/غير واضح).\n"
            f"سبب مختصر: {sig.reason}\n"
        )

    rr = sig.rr
    txt = (
        f"🎯 *Signal* — {symbol}\n"
        f"السعر: *{human_money(price)}*\n\n"
        f"*Side:* `{sig.side}`\n"
        f"*Entry:* `{human_money(sig.entry)}`\n"
        f"*SL:* `{human_money(sig.sl)}`\n"
        f"*TP1:* `{human_money(sig.tp1)}`\n"
        f"*TP2:* `{human_money(sig.tp2)}`\n"
        f"*RR (تقريباً):* `{rr:.2f}`\n"
        f"*Confidence:* `{sig.confidence}/100`\n\n"
        f"*Why:* {sig.reason}\n"
    )

    if capital:
        risk_amount, qty = position_size(capital, risk_pct, sig.entry, sig.sl)
        txt += (
            "\n*📦 Risk Management*\n"
            f"- Capital: `{human_money(capital)}`\n"
            f"- Risk: `{risk_pct}%` => `{human_money(risk_amount)}`\n"
            f"- Position size (تقريب): `{human_money(qty)}` وحدات\n"
        )

    txt += "\n⚠️ *تنبيه:* هذا محتوى تعليمي وليس نصيحة مالية."
    return txt


async def do_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol_raw: str):
    market, symbol, df, price, err = await get_market_df_and_price(symbol_raw)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return

    risk_pct = float(context.user_data.get(UD_RISK, DEFAULT_RISK_PCT))
    capital = context.user_data.get(UD_CAPITAL)

    # If we have df -> signal + chart; else -> price only
    if df is not None and len(df) >= 50:
        sig = generate_signal_from_df(df)
        chart_bytes = make_chart(df, f"{symbol} ({market})")
        await update.message.reply_photo(
            photo=chart_bytes,
            caption=f"📊 {symbol}\nالسعر: {human_money(price)}",
        )

        msg = format_signal_text(symbol, price, sig, capital, risk_pct)
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

        # Optional AI explanation
        if context.user_data.get(UD_AI, True):
            ai_txt = await ai_explain(symbol, sig, price)
            if ai_txt:
                await update.message.reply_text("🧠 *AI خطة مختصرة:*\n" + ai_txt, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"📊 {symbol}\nالسعر الحالي: {human_money(price)}\n(لا يوجد OHLCV كافي للشارت هنا)")


async def do_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol_raw: str):
    market, symbol, df, price, err = await get_market_df_and_price(symbol_raw)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return

    risk_pct = float(context.user_data.get(UD_RISK, DEFAULT_RISK_PCT))
    capital = context.user_data.get(UD_CAPITAL)

    if df is None or len(df) < 50:
        await update.message.reply_text(f"🎯 {symbol}\nالسعر: {human_money(price)}\n(ما نجمش نخرّج Signal بدون بيانات كافية)")
        return

    sig = generate_signal_from_df(df)
    msg = format_signal_text(symbol, price, sig, capital, risk_pct)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    if context.user_data.get(UD_AI, True):
        ai_txt = await ai_explain(symbol, sig, price)
        if ai_txt:
            await update.message.reply_text("🧠 *AI Explanation:*\n" + ai_txt, parse_mode=ParseMode.MARKDOWN)


async def do_scan(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol_raw: str):
    market, symbol, df, price, err = await get_market_df_and_price(symbol_raw)
    if err:
        await update.message.reply_text(f"❌ {err}")
        return
    if df is None or len(df) < 50:
        await update.message.reply_text(f"🧾 Scan {symbol}\nالسعر: {human_money(price)}\n(بيانات غير كافية)")
        return

    c = df["close"]
    r = float(rsi(c, 14).iloc[-1])
    e20 = float(ema(c, 20).iloc[-1])
    e50 = float(ema(c, 50).iloc[-1])

    bias = "صاعد ✅" if e20 > e50 else "هابط ❌"
    msg = (
        f"🧾 *Quick Scan* — {symbol}\n"
        f"- Price: `{human_money(price)}`\n"
        f"- Trend: *{bias}*\n"
        f"- RSI(14): `{r:.1f}`\n\n"
        "ملاحظة: إذا RSI فوق 70 ممكن Overbought، وإذا تحت 30 Oversold."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# -----------------------------
# Auto Paper / Auto Live Loops
# -----------------------------
async def auto_loop(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    data = job.data  # dict with user_id
    user_id = data["user_id"]

    # PTB stores user_data per user_id
    ud = context.application.user_data.get(user_id, {})
    symbol = ud.get(UD_SYMBOL)
    if not symbol:
        return

    paper_on = ud.get(UD_AUTO_PAPER, False)
    live_on = ud.get(UD_AUTO_LIVE, False)

    if not paper_on and not live_on:
        return

    # Only crypto live trading in this version (safest)
    try:
        market, sym, df, price, err = await get_market_df_and_price(symbol)
        if err or df is None:
            return
        sig = generate_signal_from_df(df)

        # Paper engine
        positions: Dict[str, Any] = ud.get(UD_POSITIONS, {})
        pos = positions.get(sym)

        # Simple paper rules: open if NONE->signal BUY/SELL, close if opposite signal
        action_msgs = []

        if paper_on:
            if pos is None and sig.side in ("BUY", "SELL"):
                positions[sym] = {
                    "side": sig.side,
                    "entry": sig.entry,
                    "ts": now_ts(),
                }
                action_msgs.append(f"🤖 *PAPER OPEN* {sym} `{sig.side}` @ `{human_money(sig.entry)}`")
            elif pos is not None:
                if sig.side != "NONE" and sig.side != pos["side"]:
                    action_msgs.append(
                        f"🤖 *PAPER CLOSE* {sym} (كانت {pos['side']}) | الآن Signal={sig.side} | Price=`{human_money(price)}`"
                    )
                    positions.pop(sym, None)

            ud[UD_POSITIONS] = positions

        # Live engine (optional) — guarded
        if live_on:
            trader = LiveTrader()
            if trader.can_trade() and market == "crypto":
                # Minimal safety: trade only when signal BUY/SELL and no existing live position tracking.
                # NOTE: This is a starter template; real position tracking needs exchange balance + open orders handling.
                live_pos = ud.get("live_pos")
                capital = ud.get(UD_CAPITAL, None)
                risk_pct = float(ud.get(UD_RISK, DEFAULT_RISK_PCT))

                if live_pos is None and sig.side in ("BUY", "SELL") and capital:
                    # Approx qty by risk model (still simplistic)
                    risk_amount, qty = position_size(float(capital), risk_pct, sig.entry, sig.sl)
                    # Convert qty to base units; for spot we buy base asset qty.
                    qty = max(qty, 0.0)
                    # Clamp small qty
                    qty = float(qty)

                    if qty > 0:
                        try:
                            order = trader.market_order(sym, sig.side, qty)
                            ud["live_pos"] = {"side": sig.side, "qty": qty, "order": order, "ts": now_ts()}
                            action_msgs.append(f"⚡ *LIVE ORDER* {sym} `{sig.side}` qty=`{human_money(qty)}` ✅")
                        except Exception as e:
                            action_msgs.append(f"⚡ *LIVE ERROR* {e}")

        # Send updates if any
        if action_msgs:
            await context.bot.send_message(chat_id=chat_id, text="\n".join(action_msgs), parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        log.warning("auto_loop error: %s", e)


def ensure_auto_job(app: Application, chat_id: int, user_id: int):
    # one repeating job per chat_id
    name = f"auto_{chat_id}"
    for j in app.job_queue.jobs():
        if j.name == name:
            return
    app.job_queue.run_repeating(
        auto_loop,
        interval=AUTO_INTERVAL_SEC,
        first=10,
        chat_id=chat_id,
        name=name,
        data={"user_id": user_id},
    )


# -----------------------------
# Message router
# -----------------------------
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # Live confirm step
    if context.user_data.get(UD_CONFIRM_LIVE, 0) == 1:
        if text.upper() == "CONFIRM LIVE":
            context.user_data[UD_AUTO_LIVE] = True
            context.user_data[UD_CONFIRM_LIVE] = 0
            context.user_data[UD_SYMBOL] = context.user_data.get(UD_SYMBOL)  # keep
            ensure_auto_job(context.application, update.effective_chat.id, update.effective_user.id)
            await update.message.reply_text("✅ تم تفعيل Auto Live. (Spot فقط / بدون رافعة)")
            return
        else:
            await update.message.reply_text("اكتب بالضبط: CONFIRM LIVE أو ألغي بـ /auto_live off")
            return

    # Buttons
    if text == "📊 تحليل":
        await analysis_btn(update, context); return
    if text == "🎯 إشارة":
        await signal_btn(update, context); return
    if text == "🧠 دردشة":
        await chat_btn(update, context); return
    if text == "⚙️ إعدادات":
        await settings(update, context); return
    if text == "🐋 Whales":
        await whales_btn(update, context); return
    if text == "🧾 Scan":
        await scan_btn(update, context); return
    if text == "🤖 Auto Paper":
        await auto_paper_btn(update, context)
        ensure_auto_job(context.application, update.effective_chat.id, update.effective_user.id)
        return
    if text == "⚡ Auto Live":
        await auto_live_btn(update, context); return

    state = context.user_data.get(STATE_KEY, STATE_NONE)

    # State actions
    if state == STATE_WAIT_SYMBOL_ANALYSIS:
        context.user_data[UD_SYMBOL] = text
        context.user_data[STATE_KEY] = STATE_NONE
        await do_analysis(update, context, text)
        return

    if state == STATE_WAIT_SYMBOL_SIGNAL:
        context.user_data[UD_SYMBOL] = text
        context.user_data[STATE_KEY] = STATE_NONE
        await do_signal(update, context, text)
        return

    if state == STATE_WAIT_SYMBOL_SCAN:
        context.user_data[UD_SYMBOL] = text
        context.user_data[STATE_KEY] = STATE_NONE
        await do_scan(update, context, text)
        return

    if state == STATE_WAIT_CHAT:
        # AI chat if enabled and available, else fallback response
        if context.user_data.get(UD_AI, True):
            client = ai_client()
            if client is not None:
                try:
                    resp = client.responses.create(model=OPENAI_MODEL, input=text)  # 2
                    out = getattr(resp, "output_text", None)
                    if out:
                        await update.message.reply_text(out)
                        return
                except Exception as e:
                    log.warning("AI chat error: %s", e)

        # fallback
        await update.message.reply_text("أنا موجود. ابعث (📊 تحليل) أو (🎯 إشارة) أو اسألني سؤال محدد.")
        return

    # Default: helpful hint
    await update.message.reply_text("اختار زر من القائمة 👇", reply_markup=MAIN_KB)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Exception: %s", context.error)
    # do not crash the bot


# -----------------------------
# Main
# -----------------------------
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("capital", cmd_capital))
    app.add_handler(CommandHandler("ai", cmd_ai))
    app.add_handler(CommandHandler("auto_paper", cmd_auto_paper))
    app.add_handler(CommandHandler("auto_live", cmd_auto_live))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.add_error_handler(error_handler)

    log.info("Bot starting...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
