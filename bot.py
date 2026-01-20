# bot.py
# -*- coding: utf-8 -*-

import os
import sys
import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import requests
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ai_engine import AIEngine, sanitize_text

# ---------- UTF-8 / logging fixes (prevents 'ascii codec' issues) ----------
def _force_utf8_stdio():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_force_utf8_stdio()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("smartbot")

# Remove bidi / invisible marks also here (extra safety)
_BIDI_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")

def clean_user_text(text: str) -> str:
    if not text:
        return ""
    text = _BIDI_RE.sub("", text)
    return text.strip()

# ---------- ENV ----------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var")

STATE_FILE = os.getenv("STATE_FILE", "state.json")

# ---------- User state ----------
@dataclass
class UserState:
    lang: str = "auto"      # auto | ar | en
    risk: float = 1.0       # 0..10
    platform: str = "binance"
    watch: str = "BTC,ETH"
    auto: bool = False      # optional (paper only)

USERS: Dict[int, UserState] = {}

def load_state():
    global USERS
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            USERS = {int(k): UserState(**v) for k, v in raw.items()}
            log.info("State loaded: %s users", len(USERS))
    except Exception as e:
        log.warning("Failed to load state: %s", e)

def save_state():
    try:
        raw = {str(uid): asdict(st) for uid, st in USERS.items()}
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("Failed to save state: %s", e)

def get_user(uid: int) -> UserState:
    if uid not in USERS:
        USERS[uid] = UserState()
        save_state()
    return USERS[uid]

# ---------- Language detection ----------
def detect_lang(auto_or_lang: str, text: str) -> str:
    if auto_or_lang in ("ar", "en"):
        return auto_or_lang
    # Auto detect: Arabic letters => ar else en
    for ch in text:
        if "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F":
            return "ar"
    return "en"

# ---------- UI keyboards ----------
def main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    if lang == "ar":
        keys = [
            [KeyboardButton("📊 تحليل"), KeyboardButton("🎯 إشارة")],
            [KeyboardButton("🐋 حيتان"), KeyboardButton("🔎 فرص")],
            [KeyboardButton("🤖 تشغيل/إيقاف Auto"), KeyboardButton("🧾 Paper")],
            [KeyboardButton("⚙️ إعدادات"), KeyboardButton("🧠 دردشة")],
        ]
    else:
        keys = [
            [KeyboardButton("📊 Analysis"), KeyboardButton("🎯 Signal")],
            [KeyboardButton("🐋 Whales"), KeyboardButton("🔎 Scan")],
            [KeyboardButton("🤖 Auto ON/OFF"), KeyboardButton("🧾 Paper")],
            [KeyboardButton("⚙️ Settings"), KeyboardButton("🧠 Chat")],
        ]
    return ReplyKeyboardMarkup(keys, resize_keyboard=True)

def settings_text(lang: str) -> str:
    if lang == "ar":
        return (
            "⚙️ الإعدادات:\n"
            "اكتب:\n"
            "/lang ar  أو  /lang en  أو  /lang auto\n"
            "/risk 0-10\n"
            "/platform binance\n"
            "/watch BTC,ETH,SOL\n"
            "/auto on  أو  /auto off\n"
        )
    return (
        "⚙️ Settings:\n"
        "Use:\n"
        "/lang ar  or  /lang en  or  /lang auto\n"
        "/risk 0-10\n"
        "/platform binance\n"
        "/watch BTC,ETH,SOL\n"
        "/auto on  or  /auto off\n"
    )

def start_text(lang: str) -> str:
    if lang == "ar":
        return (
            "✅ أهلاً! أنا SmartBot (تحليل + متابعة + دردشة تداول).\n\n"
            "الأوامر السريعة:\n"
            "📊 /analysis BTC\n"
            "🎯 /signal BTC\n"
            "🖼️ /image BTC (اختياري)\n"
            "🔎 /scan (يفحص قائمة المتابعة)\n"
            "🐋 /whales BTC (اختياري، يحتاج API)\n"
            "🧾 /paper open BTC buy 50\n"
            "🧾 /paper close\n"
            "🧾 /paper status\n"
            "🤖 /auto on أو /auto off (اختياري - Paper فقط)\n\n"
            "أو اكتب سؤالك مباشرة وسأجيب."
        )
    return (
        "✅ Welcome! I'm SmartBot (analysis + tracking + trading chat).\n\n"
        "Quick commands:\n"
        "📊 /analysis BTC\n"
        "🎯 /signal BTC\n"
        "🖼️ /image BTC (optional)\n"
        "🔎 /scan (checks watchlist)\n"
        "🐋 /whales BTC (optional, needs API)\n"
        "🧾 /paper open BTC buy 50\n"
        "🧾 /paper close\n"
        "🧾 /paper status\n"
        "🤖 /auto on or /auto off (optional - paper only)\n\n"
        "Or type any trading question and I’ll answer."
    )

# ---------- Market data (lightweight) ----------
# Crypto via CoinGecko (no key), stocks/metals via Stooq (no key).
def coingecko_price(symbol: str) -> Optional[Tuple[float, float]]:
    # returns (price_usd, change_24h_pct) if found
    try:
        sym = symbol.lower()
        # Search coin id by symbol (simple approach)
        r = requests.get("https://api.coingecko.com/api/v3/search", params={"query": sym}, timeout=15)
        r.raise_for_status()
        data = r.json()
        coins = data.get("coins", [])
        if not coins:
            return None
        coin_id = coins[0]["id"]

        r2 = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=15,
        )
        r2.raise_for_status()
        p = r2.json().get(coin_id, {})
        if "usd" not in p:
            return None
        price = float(p["usd"])
        ch = float(p.get("usd_24h_change", 0.0))
        return price, ch
    except Exception as e:
        log.warning("coingecko_price error: %s", e)
        return None

def stooq_last_close(ticker: str) -> Optional[float]:
    # Stooq daily CSV
    try:
        t = ticker.lower()
        url = f"https://stooq.com/q/d/l/?s={t}&i=d"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        if len(lines) < 2:
            return None
        last = lines[-1].split(",")
        # Date,Open,High,Low,Close,Volume
        close = float(last[4])
        return close
    except Exception as e:
        log.warning("stooq_last_close error: %s", e)
        return None

def normalize_symbol(sym: str) -> str:
    s = sym.strip().upper()
    # Common aliases
    if s in ("GOLD", "XAU", "XAUUSD"):
        return "XAUUSD"
    return s

def quick_snapshot(sym: str) -> str:
    s = normalize_symbol(sym)
    # Heuristic: if looks like stock (letters) and length<=5 => stooq ticker might need .us
    # We'll try crypto first; if not found try stooq.
    cg = coingecko_price(s)
    if cg:
        price, ch = cg
        return f"{s} (Crypto)\nPrice: ${price:,.6f}\n24h: {ch:+.2f}%"
    # Stooq mapping examples:
    # TSLA.US , AAPL.US , XAUUSD
    st = None
    if s.isalpha() and len(s) <= 5:
        st = stooq_last_close(f"{s}.US")
        if st is not None:
            return f"{s} (Stock)\nLast close: ${st:,.2f}"
    if s == "XAUUSD":
        st = stooq_last_close("xauusd")
        if st is not None:
            return f"XAUUSD (Gold)\nLast close: ${st:,.2f}"
    # fallback try stooq raw
    st = stooq_last_close(s)
    if st is not None:
        return f"{s}\nLast close: {st:,.4f}"
    return f"{s}\nData not available right now."

# ---------- Charts ----------
def make_simple_chart(symbol: str) -> Optional[str]:
    """
    Creates a simple chart image file path for the symbol (crypto only).
    """
    s = normalize_symbol(symbol)
    try:
        # Use CoinGecko market_chart (crypto only)
        r = requests.get("https://api.coingecko.com/api/v3/search", params={"query": s.lower()}, timeout=15)
        r.raise_for_status()
        coins = r.json().get("coins", [])
        if not coins:
            return None
        coin_id = coins[0]["id"]

        r2 = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": 7},
            timeout=20,
        )
        r2.raise_for_status()
        prices = r2.json().get("prices", [])
        if len(prices) < 5:
            return None

        y = [p[1] for p in prices]
        x = list(range(len(y)))

        plt.figure(figsize=(8, 3))
        plt.plot(x, y)
        plt.title(f"{s} - 7d (USD)")
        plt.tight_layout()

        out = f"/tmp/{s}_7d.png"
        plt.savefig(out, dpi=160)
        plt.close()
        return out
    except Exception as e:
        log.warning("make_simple_chart error: %s", e)
        return None

# ---------- Paper trading (simulation only) ----------
PAPER_TRADES: Dict[int, Dict[str, object]] = {}

def paper_open(uid: int, symbol: str, side: str, amount: float) -> str:
    symbol = normalize_symbol(symbol)
    side = side.lower()
    if side not in ("buy", "sell"):
        return "Side must be buy/sell"
    PAPER_TRADES[uid] = {"symbol": symbol, "side": side, "amount": float(amount), "status": "OPEN"}
    return f"✅ Paper trade opened: {symbol} {side.upper()} ${amount:.2f}"

def paper_close(uid: int) -> str:
    tr = PAPER_TRADES.get(uid)
    if not tr:
        return "⚠️ No open paper trade."
    tr["status"] = "CLOSED"
    return f"❌ Paper trade closed: {tr['symbol']}"

def paper_status(uid: int) -> str:
    tr = PAPER_TRADES.get(uid)
    if not tr:
        return "📭 No paper trades."
    return f"🧾 Paper Status:\nSymbol: {tr['symbol']}\nSide: {tr['side']}\nAmount: ${tr['amount']:.2f}\nStatus: {tr['status']}"

# ---------- AI ----------
AI: Optional[AIEngine] = None

def get_ai() -> AIEngine:
    global AI
    if AI is None:
        AI = AIEngine()
    return AI

# ---------- Handlers ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = detect_lang(u.lang, "مرحبا") if u.lang != "en" else "en"
    await update.message.reply_text(start_text(lang), reply_markup=main_keyboard(lang))

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = detect_lang(u.lang, update.message.text or "")
    await update.message.reply_text(settings_text(lang), reply_markup=main_keyboard(lang))

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    arg = (context.args[0].lower() if context.args else "").strip()
    if arg not in ("ar", "en", "auto"):
        # also accept Arabic words
        txt = clean_user_text(update.message.text or "")
        if "عربي" in txt:
            arg = "ar"
        elif "english" in txt or "انجليزي" in txt:
            arg = "en"
        else:
            arg = "auto"
    u.lang = arg
    save_state()
    lang = detect_lang(u.lang, update.message.text or "")
    msg = "✅ تم ضبط اللغة: " + arg if lang == "ar" else "✅ Language set to: " + arg
    await update.message.reply_text(msg, reply_markup=main_keyboard(lang))

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = detect_lang(u.lang, update.message.text or "")
    try:
        val = float(context.args[0]) if context.args else None
        if val is None:
            raise ValueError("missing")
        val = max(0.0, min(10.0, val))
        u.risk = val
        save_state()
        await update.message.reply_text(
            (f"✅ تم ضبط المخاطرة: {val}" if lang == "ar" else f"✅ Risk set to: {val}"),
            reply_markup=main_keyboard(lang),
        )
    except Exception:
        await update.message.reply_text("مثال: /risk 2" if lang == "ar" else "Example: /risk 2")

async def cmd_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = detect_lang(u.lang, update.message.text or "")
    p = (context.args[0].lower() if context.args else "binance")
    u.platform = p
    save_state()
    await update.message.reply_text(
        (f"✅ تم اختيار المنصة: {p}" if lang == "ar" else f"✅ Platform set: {p}"),
        reply_markup=main_keyboard(lang),
    )

async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = detect_lang(u.lang, update.message.text or "")
    txt = " ".join(context.args) if context.args else ""
    txt = clean_user_text(txt)
    if not txt:
        await update.message.reply_text("مثال: /watch BTC,ETH,SOL" if lang == "ar" else "Example: /watch BTC,ETH,SOL")
        return
    u.watch = txt.replace(" ", "")
    save_state()
    await update.message.reply_text(
        (f"👀 تم ضبط Watchlist: {u.watch}" if lang == "ar" else f"👀 Watchlist set: {u.watch}"),
        reply_markup=main_keyboard(lang),
    )

async def cmd_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    raw = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, raw)
    sym = context.args[0] if context.args else (raw.replace("📊", "").replace("تحليل", "").replace("Analysis", "").strip() or "BTC")
    sym = normalize_symbol(sym)

    snap = quick_snapshot(sym)
    hint = f"User risk preference (0-10): {u.risk}\nPlatform: {u.platform}\nSnapshot:\n{snap}"
    try:
        ai = get_ai()
        prompt = f"حلل {sym} الآن مع إدارة مخاطر واضحة ونقاط مراقبة." if lang == "ar" else f"Analyze {sym} now with clear risk management and key levels to watch."
        ans = ai.answer(lang=lang, user_text=prompt, context_hint=hint)
        await update.message.reply_text(ans, reply_markup=main_keyboard(lang))
    except Exception as e:
        await update.message.reply_text(
            ("❌ حصل خطأ في الذكاء الاصطناعي. حاول لاحقاً." if lang == "ar" else "❌ AI error. Try again later."),
            reply_markup=main_keyboard(lang),
        )
        log.exception("AI analysis error: %s", e)

async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    raw = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, raw)
    sym = context.args[0] if context.args else "BTC"
    sym = normalize_symbol(sym)

    snap = quick_snapshot(sym)
    hint = f"Risk (0-10): {u.risk}\nSnapshot:\n{snap}"
    try:
        ai = get_ai()
        prompt = (
            f"اعطني إشارة تداول تعليمية لـ {sym} (سيناريو شراء/بيع) مع نقاط دخول/خروج وإيقاف خسارة بشكل غير إلزامي."
            if lang == "ar"
            else f"Give an educational trade signal for {sym} with scenarios (bull/bear), entries/exits and stop-loss (not financial advice)."
        )
        ans = ai.answer(lang=lang, user_text=prompt, context_hint=hint)
        await update.message.reply_text(ans, reply_markup=main_keyboard(lang))
    except Exception as e:
        await update.message.reply_text(
            ("❌ خطأ AI." if lang == "ar" else "❌ AI error."),
            reply_markup=main_keyboard(lang),
        )
        log.exception("AI signal error: %s", e)

async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    raw = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, raw)
    sym = context.args[0] if context.args else "BTC"
    sym = normalize_symbol(sym)

    path = make_simple_chart(sym)
    if not path:
        await update.message.reply_text(
            ("❌ لم أستطع توليد صورة الآن." if lang == "ar" else "❌ Couldn't generate an image right now."),
            reply_markup=main_keyboard(lang),
        )
        return

    caption = (f"🖼️ {sym} - 7 أيام" if lang == "ar" else f"🖼️ {sym} - 7 days")
    with open(path, "rb") as f:
        await update.message.reply_photo(photo=InputFile(f), caption=caption, reply_markup=main_keyboard(lang))

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    raw = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, raw)
    watch = [normalize_symbol(x) for x in u.watch.split(",") if x.strip()]
    if not watch:
        watch = ["BTC", "ETH"]

    lines: List[str] = []
    for s in watch[:10]:
        snap = quick_snapshot(s)
        lines.append(snap)

    header = "🔎 فرص (حسب قائمة المتابعة):\n\n" if lang == "ar" else "🔎 Scan (from your watchlist):\n\n"
    await update.message.reply_text(header + "\n\n".join(lines), reply_markup=main_keyboard(lang))

async def cmd_whales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    raw = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, raw)
    api_key = os.getenv("WHALEALERT_API_KEY", "").strip()
    if not api_key:
        await update.message.reply_text(
            ("🐋 ميزة الحيتان تحتاج WHALEALERT_API_KEY (اختياري). حالياً غير مفعّلة."
             if lang == "ar" else
             "🐋 Whales feature needs WHALEALERT_API_KEY (optional). It’s disabled for now."),
            reply_markup=main_keyboard(lang),
        )
        return
    sym = context.args[0] if context.args else "BTC"
    sym = normalize_symbol(sym)
    # Minimal placeholder (you can extend)
    await update.message.reply_text(
        ("🐋 قريباً: تتبع الحيتان مفعّل، لكن يلزم تطوير حسب الـ API." if lang == "ar" else "🐋 Enabled, but needs API-specific implementation."),
        reply_markup=main_keyboard(lang),
    )

async def cmd_paper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    raw = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, raw)

    if not context.args:
        await update.message.reply_text(
            ("استخدم:\n/paper open BTC buy 50\n/paper close\n/paper status"
             if lang == "ar" else
             "Use:\n/paper open BTC buy 50\n/paper close\n/paper status"),
            reply_markup=main_keyboard(lang),
        )
        return

    sub = context.args[0].lower()
    if sub == "open" and len(context.args) >= 4:
        sym = context.args[1]
        side = context.args[2]
        amt = float(context.args[3])
        msg = paper_open(uid, sym, side, amt)
        await update.message.reply_text(msg, reply_markup=main_keyboard(lang))
        return
    if sub == "close":
        msg = paper_close(uid)
        await update.message.reply_text(msg, reply_markup=main_keyboard(lang))
        return
    if sub == "status":
        msg = paper_status(uid)
        await update.message.reply_text(msg, reply_markup=main_keyboard(lang))
        return

    await update.message.reply_text(
        ("صيغة غير صحيحة. مثال: /paper open BTC buy 50" if lang == "ar" else "Bad format. Example: /paper open BTC buy 50"),
        reply_markup=main_keyboard(lang),
    )

async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    raw = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, raw)
    arg = (context.args[0].lower() if context.args else "").strip()
    if arg in ("on", "1", "true"):
        u.auto = True
    elif arg in ("off", "0", "false"):
        u.auto = False
    save_state()
    if lang == "ar":
        state = "✅ مفعّل (Paper)" if u.auto else "⛔ متوقف"
        await update.message.reply_text(f"🤖 Auto: {state}", reply_markup=main_keyboard(lang))
    else:
        state = "✅ ON (Paper)" if u.auto else "⛔ OFF"
        await update.message.reply_text(f"🤖 Auto: {state}", reply_markup=main_keyboard(lang))

# ---------- Text router (buttons + free chat) ----------
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    txt = clean_user_text(update.message.text or "")
    lang = detect_lang(u.lang, txt)

    # Button mapping
    if txt in ("⚙️ إعدادات", "⚙️ Settings"):
        await update.message.reply_text(settings_text(lang), reply_markup=main_keyboard(lang))
        return
    if txt in ("🧠 دردشة", "🧠 Chat"):
        await update.message.reply_text(
            ("🧠 اكتب سؤالك الآن." if lang == "ar" else "🧠 Ask your question now."),
            reply_markup=main_keyboard(lang),
        )
        return
    if txt in ("📊 تحليل", "📊 Analysis"):
        # Ask for symbol
        await update.message.reply_text(
            ("أرسل الرمز: BTC / ETH / TSLA / XAUUSD" if lang == "ar" else "Send symbol: BTC / ETH / TSLA / XAUUSD"),
            reply_markup=main_keyboard(lang),
        )
        return
    if txt in ("🎯 إشارة", "🎯 Signal"):
        await update.message.reply_text(
            ("أرسل الرمز أو استخدم /signal BTC" if lang == "ar" else "Send a symbol or use /signal BTC"),
            reply_markup=main_keyboard(lang),
        )
        return
    if txt in ("🔎 فرص", "🔎 Scan"):
        await cmd_scan(update, context)
        return
    if txt in ("🐋 حيتان", "🐋 Whales"):
        await update.message.reply_text(
            ("استخدم /whales BTC (اختياري)" if lang == "ar" else "Use /whales BTC (optional)"),
            reply_markup=main_keyboard(lang),
        )
        return
    if txt in ("🧾 Paper",):
        await update.message.reply_text(
            ("استخدم:\n/paper open BTC buy 50\n/paper close\n/paper status" if lang == "ar"
             else "Use:\n/paper open BTC buy 50\n/paper close\n/paper status"),
            reply_markup=main_keyboard(lang),
        )
        return
    if txt in ("🤖 تشغيل/إيقاف Auto", "🤖 Auto ON/OFF"):
        # Toggle quickly
        u.auto = not u.auto
        save_state()
        await cmd_auto(update, context)
        return

    # If message looks like a symbol only => do quick analysis
    if re.fullmatch(r"[A-Za-z]{2,6}(\.?[A-Za-z]{0,4})", txt) or txt.upper() in ("BTC", "ETH", "SOL", "TSLA", "XAUUSD", "XAU", "GOLD"):
        context.args = [txt]  # hack to reuse cmd_analysis
        await cmd_analysis(update, context)
        return

    # Otherwise: AI free chat
    try:
        ai = get_ai()
        # Provide snapshot context from watchlist first coin
        first = normalize_symbol((u.watch.split(",")[0] if u.watch else "BTC"))
        snap = quick_snapshot(first)
        hint = f"User settings: risk={u.risk}, platform={u.platform}, watchlist={u.watch}\nQuick snapshot:\n{snap}"
        ans = ai.answer(lang=lang, user_text=txt, context_hint=hint)
        await update.message.reply_text(ans, reply_markup=main_keyboard(lang))
    except Exception as e:
        # Never show raw encoding crash to user
        await update.message.reply_text(
            ("❌ حصل خطأ في الذكاء الاصطناعي. حاول لاحقاً." if lang == "ar" else "❌ AI error. Try again later."),
            reply_markup=main_keyboard(lang),
        )
        log.exception("AI chat error: %s", e)

# ---------- Error handler ----------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    try:
        log.exception("Unhandled error: %s", context.error)
    except Exception:
        pass

def main():
    load_state()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("platform", cmd_platform))
    app.add_handler(CommandHandler("watch", cmd_watch))

    app.add_handler(CommandHandler("analysis", cmd_analysis))
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CommandHandler("image", cmd_image))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("whales", cmd_whales))

    app.add_handler(CommandHandler("paper", cmd_paper))
    app.add_handler(CommandHandler("auto", cmd_auto))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.add_error_handler(on_error)

    log.info("🤖 AI BOT RUNNING ...")
    # Polling: must ensure only ONE instance runs, otherwise Telegram Conflict happens.
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
