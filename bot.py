# bot.py
import os
import logging
import tempfile
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from ai_engine import AIEngine, clean_text

# -----------------------
# Logging (UTF-8 safe)
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("smartbot")


# -----------------------
# Config
# -----------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var")

AUTO_INTERVAL_SEC = int(os.getenv("AUTO_INTERVAL_SEC", "900"))  # 15min default
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "ar").strip().lower()

ai = AIEngine()


# -----------------------
# User state
# -----------------------
@dataclass
class UserState:
    mode: str = "idle"          # idle | analysis | chat | signal
    lang: str = DEFAULT_LANG    # ar/en
    auto: bool = False          # paper auto alerts on/off
    watch_symbol: Optional[str] = None  # for auto paper signals


USERS: Dict[int, UserState] = {}


def get_user(uid: int) -> UserState:
    if uid not in USERS:
        USERS[uid] = UserState()
    return USERS[uid]


# -----------------------
# Helpers: symbol mapping
# -----------------------
def normalize_symbol(s: str) -> Tuple[str, str]:
    """
    Returns (kind, yf_symbol)
    kind: crypto | stock | gold
    Accepts: BTC, ETH, SOL, TSLA, AAPL, XAUUSD, GOLD
    """
    s = clean_text(s).upper().replace("/", "").replace(" ", "")

    # Gold
    if s in ("XAUUSD", "GOLD", "XAU"):
        return "gold", "XAUUSD=X"

    # Crypto common
    crypto_map = {
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "SOL": "SOL-USD",
        "BNB": "BNB-USD",
        "XRP": "XRP-USD",
        "DOGE": "DOGE-USD",
    }
    if s in crypto_map:
        return "crypto", crypto_map[s]

    # If user already sent like BTCUSDT => try convert
    if s.endswith("USDT") and len(s) > 4:
        base = s[:-4]
        return "crypto", f"{base}-USD"

    # default treat as stock ticker
    # TSLA, AAPL, MSFT, etc.
    return "stock", s


def fetch_ohlc(yf_symbol: str, period: str = "7d", interval: str = "1h") -> pd.DataFrame:
    df = yf.download(yf_symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        # fallback wider
        df = yf.download(yf_symbol, period="30d", interval="1d", progress=False)
    if df is None or df.empty:
        raise ValueError("No market data found for symbol")
    return df


def generate_chart(yf_symbol: str, title: str) -> str:
    df = fetch_ohlc(yf_symbol)
    close = df["Close"].dropna()

    # Simple chart
    fig = plt.figure(figsize=(10, 4))
    plt.plot(close.index, close.values)
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.tight_layout()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    fig.savefig(tmp.name, dpi=160)
    plt.close(fig)
    return tmp.name


def simple_signal(df: pd.DataFrame) -> str:
    """
    Educational paper signal: SMA cross
    """
    close = df["Close"].dropna()
    if len(close) < 50:
        return "📌 بيانات غير كافية لإشارة موثوقة الآن."

    sma_fast = close.rolling(10).mean()
    sma_slow = close.rolling(30).mean()

    latest = close.index[-1]
    f_now = float(sma_fast.iloc[-1])
    s_now = float(sma_slow.iloc[-1])
    price = float(close.iloc[-1])

    if f_now > s_now:
        bias = "📈 اتجاه صاعد (Paper)"
        idea = "فكرة: انتظار تصحيح خفيف ثم متابعة الاتجاه."
    elif f_now < s_now:
        bias = "📉 اتجاه هابط (Paper)"
        idea = "فكرة: تجنّب الشراء العشوائي، وراقب كسر/استرجاع مستويات."
    else:
        bias = "➖ محايد (Paper)"
        idea = "فكرة: انتظر إشارة أوضح."

    return (
        f"{bias}\n"
        f"السعر الحالي (تقريبي): {price:.4f}\n"
        f"SMA10: {f_now:.4f} | SMA30: {s_now:.4f}\n"
        f"💡 {idea}\n"
        "⚠️ تعليم فقط وليس توصية مالية."
    )


# -----------------------
# Prompts (AI)
# -----------------------
def system_prompt_ar(mode: str) -> str:
    base = (
        "أنت مساعد تداول تعليمي داخل بوت تيليجرام. "
        "لا تقدّم أوامر تنفيذ تداول حقيقية، ولا تعد بأرباح، "
        "وقدّم دائماً تنبيه: (تعليمي وليس نصيحة مالية). "
        "اكتب بالعربية الواضحة، مختصر ومنظم."
    )

    if mode == "analysis":
        return base + (
            "\nالمطلوب: تحليل فني مبسط: اتجاه، دعم/مقاومة، سيناريو صعود/هبوط، "
            "وخطة إدارة مخاطر بدون رافعة."
        )
    if mode == "chat":
        return base + "\nالمطلوب: أجب على أسئلة المستخدم عن التداول بشكل تعليمي."
    if mode == "signal":
        return base + "\nالمطلوب: قدّم إشارة تعليمية paper (دخول/خروج افتراضي) مع شرح."
    return base


# -----------------------
# UI
# -----------------------
def main_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ar":
        rows = [
            [InlineKeyboardButton("📊 تحليل", callback_data="mode:analysis"),
             InlineKeyboardButton("🎯 إشارة", callback_data="mode:signal")],
            [InlineKeyboardButton("🤖 Auto Paper", callback_data="auto:toggle"),
             InlineKeyboardButton("🧠 دردشة", callback_data="mode:chat")],
            [InlineKeyboardButton("⚙️ إعدادات", callback_data="settings")]
        ]
    else:
        rows = [
            [InlineKeyboardButton("📊 Analysis", callback_data="mode:analysis"),
             InlineKeyboardButton("🎯 Signal", callback_data="mode:signal")],
            [InlineKeyboardButton("🤖 Auto Paper", callback_data="auto:toggle"),
             InlineKeyboardButton("🧠 Chat", callback_data="mode:chat")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ]
    return InlineKeyboardMarkup(rows)


# -----------------------
# Handlers
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    text = (
        "🤖 Smart Trading Bot\n\n"
        "اختر وضع:\n"
        "📊 تحليل • 🎯 إشارة • 🧠 دردشة • 🤖 Auto Paper\n\n"
        "أرسل رمز مثل: BTC / ETH / TSLA / XAUUSD"
        if u.lang == "ar"
        else
        "🤖 Smart Trading Bot\n\nChoose mode:\nAnalysis • Signal • Chat • Auto Paper\n\nSend symbol: BTC / ETH / TSLA / XAUUSD"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(u.lang))


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    u = get_user(uid)

    data = query.data or ""
    if data.startswith("mode:"):
        u.mode = data.split(":", 1)[1]
        if u.lang == "ar":
            msg = "✅ تم. أرسل الرمز الآن مثل: BTC / ETH / TSLA / XAUUSD"
        else:
            msg = "✅ Done. Send a symbol: BTC / ETH / TSLA / XAUUSD"
        await query.edit_message_text(msg, reply_markup=main_keyboard(u.lang))
        return

    if data == "auto:toggle":
        u.auto = not u.auto
        state = "✅ ON (Paper)" if u.auto else "⛔ OFF"
        if u.lang == "ar":
            msg = f"🤖 Auto Paper: {state}\n\nأرسل رمز للمتابعة التلقائية (مثال BTC)."
        else:
            msg = f"🤖 Auto Paper: {state}\n\nSend a symbol to auto-watch (e.g. BTC)."
        await query.edit_message_text(msg, reply_markup=main_keyboard(u.lang))
        return

    if data == "settings":
        u.lang = "en" if u.lang == "ar" else "ar"
        msg = "⚙️ تم تغيير اللغة." if u.lang == "ar" else "⚙️ Language switched."
        await query.edit_message_text(msg, reply_markup=main_keyboard(u.lang))
        return


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    text = clean_text(update.message.text or "")
    if not text:
        return

    # If Auto is ON and user sends symbol => set watch symbol
    # (also works even if mode is analysis/chat/signal)
    maybe_kind, yf_symbol = normalize_symbol(text)
    if u.auto and len(text) <= 12:
        u.watch_symbol = yf_symbol
        if u.lang == "ar":
            await update.message.reply_text(
                f"✅ تم تفعيل المراقبة التلقائية (Paper) على: {text.upper()}\n"
                f"سأرسل تنبيه كل {AUTO_INTERVAL_SEC//60} دقيقة.",
                reply_markup=main_keyboard(u.lang),
            )
        else:
            await update.message.reply_text(
                f"✅ Auto watch set (Paper): {text.upper()}\n"
                f"I will notify every {AUTO_INTERVAL_SEC//60} min.",
                reply_markup=main_keyboard(u.lang),
            )
        return

    # Mode behavior
    if u.mode in ("analysis", "signal"):
        # Interpret as symbol
        try:
            kind, yf_sym = normalize_symbol(text)
            df = fetch_ohlc(yf_sym)
            chart_path = generate_chart(yf_sym, title=f"{text.upper()} ({yf_sym})")

            # Send chart
            with open(chart_path, "rb") as f:
                caption = f"📊 {text.upper()} Chart"
                await update.message.reply_photo(photo=f, caption=caption)

            # Compose base signal
            sig = simple_signal(df)

            # Ask AI to write nicer explanation (safe fallback)
            prompt = (
                f"الأصل: {text.upper()} ({yf_sym})\n"
                f"هذه إشارة/ملخص مبني على SMA:\n{sig}\n\n"
                "اكتب تحليل مبسط + نقاط دعم/مقاومة تقريبية + سيناريوهين + إدارة مخاطر بدون رافعة."
                if u.lang == "ar" else
                f"Asset: {text.upper()} ({yf_sym})\nSMA summary:\n{sig}\n\nWrite an educational analysis and risk plan (no leverage)."
            )

            sys_p = system_prompt_ar(u.mode) if u.lang == "ar" else (
                "You are an educational trading assistant in a Telegram bot. "
                "No guaranteed profits. Always include: Educational, not financial advice."
            )

            ai_text = ai.chat(prompt, sys_p)

            # If AI unavailable, at least send the SMA signal
            if not ai.available():
                await update.message.reply_text(sig)
                return

            await update.message.reply_text(ai_text)
            return

        except Exception as e:
            log.exception("Analysis error: %s", e)
            msg = "❌ حصل خطأ في جلب البيانات/الرسم. جرّب رمز آخر." if u.lang == "ar" else "❌ Error fetching data/chart. Try another symbol."
            await update.message.reply_text(msg, reply_markup=main_keyboard(u.lang))
            return

    # Chat mode or idle => AI chat (safe fallback)
    sys_p = system_prompt_ar("chat") if u.lang == "ar" else (
        "You are a helpful educational trading assistant. Always add a short disclaimer."
    )
    answer = ai.chat(text, sys_p)
    await update.message.reply_text(answer, reply_markup=main_keyboard(u.lang))


# -----------------------
# Auto job (Paper alerts)
# -----------------------
async def auto_job(context: ContextTypes.DEFAULT_TYPE):
    # Send periodic paper signals to users who enabled auto & set watch_symbol
    app: Application = context.application
    for uid, u in list(USERS.items()):
        if not u.auto or not u.watch_symbol:
            continue
        try:
            df = fetch_ohlc(u.watch_symbol)
            sig = simple_signal(df)
            # Push message
            await app.bot.send_message(
                chat_id=uid,
                text=f"🤖 Auto Paper Alert\n{sig}",
            )
        except Exception as e:
            log.warning("Auto job failed for %s: %s", uid, e)


def build_app() -> Application:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(on_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # JobQueue (requires python-telegram-bot[job-queue])
    application.job_queue.run_repeating(auto_job, interval=AUTO_INTERVAL_SEC, first=30)

    return application


def main():
    app = build_app()

    # ⚠️ مهم: تجنّب خطأ Conflict
    # لا تشغل نفس البوت في جهازك + Railway في نفس الوقت.
    # شغل instance واحدة فقط.
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
