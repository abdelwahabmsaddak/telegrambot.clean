# bot.py
# -*- coding: utf-8 -*-

import os
import logging
import re
import sys
from typing import Dict, Any, List

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ai_engine import AIEngine, sanitize_text


# --- Force UTF-8 stdout ---
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("smartbot")


# --- Simple in-memory user state ---
_USERS: Dict[int, Dict[str, Any]] = {}

DEFAULT_USER = {
    "lang": "auto",          # auto | ar | en
    "risk": 1.0,             # 0.5 .. 3.0 (example)
    "auto": False,           # auto trading (paper) optional
    "watch": ["BTC", "ETH"], # watchlist
    "history": [],           # chat history
}


def get_user(uid: int) -> Dict[str, Any]:
    if uid not in _USERS:
        _USERS[uid] = dict(DEFAULT_USER)
    return _USERS[uid]


def push_history(u: Dict[str, Any], role: str, content: str):
    u["history"].append({"role": role, "content": sanitize_text(content)})
    u["history"] = u["history"][-12:]


def detect_lang(text: str, mode: str) -> str:
    if mode != "auto":
        return mode
    if re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text or ""):
        return "ar"
    return "en"


def ui_keyboard(lang: str) -> ReplyKeyboardMarkup:
    # One language per layout (no mixing)
    if lang == "ar":
        keys = [
            [KeyboardButton("📊 تحليل"), KeyboardButton("🎯 إشارة")],
            [KeyboardButton("🐋 حيتان"), KeyboardButton("🔎 فرص")],
            [KeyboardButton("🤖 Auto تشغيل/إيقاف"), KeyboardButton("🧾 Paper")],
            [KeyboardButton("⚙️ إعدادات"), KeyboardButton("🧠 دردشة")],
        ]
    else:
        keys = [
            [KeyboardButton("📊 Analysis"), KeyboardButton("🎯 Signal")],
            [KeyboardButton("🐋 Whales"), KeyboardButton("🔎 Scan")],
            [KeyboardButton("🤖 Auto ON/OFF"), KeyboardButton("🧾 Paper")],
            [KeyboardButton("⚙️ Settings"), KeyboardButton("🧠 Chat")],
        ]
    return ReplyKeyboardMarkup(keys, resize_keyboard=True, is_persistent=True)


def help_text(lang: str) -> str:
    if lang == "ar":
        return (
            "👋 مرحبًا! هذا بوت تداول ذكي.\n\n"
            "✅ الأوامر:\n"
            "/start — تشغيل\n"
            "/lang ar أو /lang en أو /lang auto — اللغة\n"
            "/risk 1.0 — مستوى المخاطرة\n"
            "/watch BTC,ETH,SOL — قائمة المراقبة\n"
            "/analysis BTC — تحليل أصل\n"
            "/signal BTC — فكرة صفقة تعليمية\n"
            "/whales BTC — ملخص نشاط حيتان (مبسّط)\n"
            "/scan — يرشّح فرص من قائمة المراقبة (مبسّط)\n"
            "/auto on أو /auto off — تفعيل/إيقاف Paper Auto (اختياري)\n\n"
            "🧠 يمكنك أيضًا تسأل أي سؤال تداول عادي في الدردشة."
        )
    return (
        "👋 Welcome! This is a smart trading bot.\n\n"
        "✅ Commands:\n"
        "/start — start\n"
        "/lang ar | en | auto — language\n"
        "/risk 1.0 — risk level\n"
        "/watch BTC,ETH,SOL — watchlist\n"
        "/analysis BTC — asset analysis\n"
        "/signal BTC — educational trade idea\n"
        "/whales BTC — whale activity summary (simple)\n"
        "/scan — scan watchlist for opportunities (simple)\n"
        "/auto on | off — enable/disable paper auto (optional)\n\n"
        "🧠 You can also ask any trading question in chat."
    )


# --------- Placeholder "market" logic (simple) ----------
def simple_analysis(symbol: str, lang: str, risk: float) -> str:
    symbol = symbol.upper().strip()
    if lang == "ar":
        return (
            f"📊 تحليل مبسّط لـ {symbol}\n"
            f"- مستوى المخاطرة الحالي: {risk}\n"
            "- راقب: الاتجاه العام (Trend)، الدعوم/المقاومات، حجم التداول.\n"
            "- خطة مخاطرة: لا تخاطر بأكثر من 1-2% من رأس المال في الصفقة.\n"
            "إذا تحب، اكتب الإطار الزمني (1H / 4H / 1D) ونوع تداولك (سكالب/سوينغ)."
        )
    return (
        f"📊 Simple analysis for {symbol}\n"
        f"- Current risk level: {risk}\n"
        "- Watch: trend, key support/resistance, volume.\n"
        "- Risk plan: avoid risking >1–2% per trade.\n"
        "Tell me timeframe (1H/4H/1D) and your style (scalp/swing) for a better plan."
    )


def simple_signal(symbol: str, lang: str, risk: float) -> str:
    symbol = symbol.upper().strip()
    if lang == "ar":
        return (
            f"🎯 إشارة تعليمية لـ {symbol}\n"
            "- الفكرة: انتظر كسر مقاومة/ارتداد من دعم (حسب الشارت).\n"
            f"- مخاطرة: {risk}\n"
            "- دخول: بعد تأكيد.\n"
            "- وقف: تحت آخر قاع/فوق آخر قمة.\n"
            "- هدف: 1R ثم 2R.\n"
            "⚠️ هذه ليست نصيحة مالية، فقط تعليم."
        )
    return (
        f"🎯 Educational signal for {symbol}\n"
        "- Idea: wait for resistance break or support bounce (chart-based).\n"
        f"- Risk: {risk}\n"
        "- Entry: after confirmation.\n"
        "- Stop: below last swing low / above last swing high.\n"
        "- Targets: 1R then 2R.\n"
        "⚠️ Not financial advice. Educational only."
    )


def simple_whales(symbol: str, lang: str) -> str:
    symbol = symbol.upper().strip()
    if lang == "ar":
        return (
            f"🐋 حيتان (مبسّط) لـ {symbol}\n"
            "- إذا شفت شموع قوية + حجم عالي: قد يكون تجميع/تصريف.\n"
            "- راقب: تحركات مفاجئة + كسر مستويات مهمّة.\n"
            "إذا عندك رابط/سكرين من منصة التحليل ابعثه ونفسّر أكثر."
        )
    return (
        f"🐋 Whales (simple) for {symbol}\n"
        "- Strong candles + high volume can indicate accumulation/distribution.\n"
        "- Watch: sudden spikes and key level breaks.\n"
        "Share a chart screenshot/link for a deeper read."
    )


def simple_scan(watch: List[str], lang: str) -> str:
    if lang == "ar":
        return "🔎 فرص (مبسّط):\n" + "\n".join([f"- راقب {s.upper()} قرب دعم/مقاومة" for s in watch])
    return "🔎 Scan (simple):\n" + "\n".join([f"- Watch {s.upper()} near support/resistance" for s in watch])


# ----------------- Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    lang = u["lang"]
    # show keyboard in a concrete language (if auto -> infer from user name/last msg? default en)
    kb_lang = "ar" if lang == "ar" else ("en" if lang == "en" else "en")

    await update.message.reply_text(help_text(kb_lang), reply_markup=ui_keyboard(kb_lang))


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    arg = (context.args[0].lower().strip() if context.args else "auto")
    if arg not in ("auto", "ar", "en"):
        arg = "auto"
    u["lang"] = arg

    kb_lang = "ar" if arg == "ar" else ("en" if arg == "en" else "en")
    if kb_lang == "ar":
        await update.message.reply_text("✅ تم ضبط اللغة: " + arg, reply_markup=ui_keyboard("ar"))
    else:
        await update.message.reply_text("✅ Language set to: " + arg, reply_markup=ui_keyboard("en"))


async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    val = 1.0
    if context.args:
        try:
            val = float(context.args[0])
        except Exception:
            val = u["risk"]
    val = max(0.3, min(3.0, val))
    u["risk"] = val

    lang = "ar" if u["lang"] == "ar" else "en"
    if lang == "ar":
        await update.message.reply_text(f"✅ تم ضبط المخاطرة: {val}")
    else:
        await update.message.reply_text(f"✅ Risk set to: {val}")


async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    raw = " ".join(context.args) if context.args else ""
    raw = raw.replace(" ", "")
    items = [x.strip().upper() for x in raw.split(",") if x.strip()]
    if items:
        u["watch"] = items[:20]

    lang = "ar" if u["lang"] == "ar" else "en"
    if lang == "ar":
        await update.message.reply_text("👀 تم ضبط قائمة المراقبة: " + ", ".join(u["watch"]))
    else:
        await update.message.reply_text("👀 Watchlist set: " + ", ".join(u["watch"]))


async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    arg = (context.args[0].lower().strip() if context.args else "")
    if arg in ("on", "1", "true"):
        u["auto"] = True
    elif arg in ("off", "0", "false"):
        u["auto"] = False

    lang = "ar" if u["lang"] == "ar" else "en"
    if lang == "ar":
        state = "✅ مفعّل (Paper)" if u["auto"] else "⛔ متوقف"
        await update.message.reply_text(f"🤖 Auto: {state}")
    else:
        state = "✅ ON (Paper)" if u["auto"] else "⛔ OFF"
        await update.message.reply_text(f"🤖 Auto: {state}")


async def cmd_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    symbol = (context.args[0] if context.args else (u["watch"][0] if u["watch"] else "BTC"))
    lang = detect_lang(symbol, u["lang"])
    await update.message.reply_text(simple_analysis(symbol, "ar" if lang == "ar" else "en", u["risk"]))


async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    symbol = (context.args[0] if context.args else (u["watch"][0] if u["watch"] else "BTC"))
    lang = detect_lang(symbol, u["lang"])
    await update.message.reply_text(simple_signal(symbol, "ar" if lang == "ar" else "en", u["risk"]))


async def cmd_whales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    symbol = (context.args[0] if context.args else (u["watch"][0] if u["watch"] else "BTC"))
    lang = detect_lang(symbol, u["lang"])
    await update.message.reply_text(simple_whales(symbol, "ar" if lang == "ar" else "en"))


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    lang = "ar" if u["lang"] == "ar" else "en"
    await update.message.reply_text(simple_scan(u["watch"], lang))


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = "ar" if u["lang"] == "ar" else "en"

    if lang == "ar":
        await update.message.reply_text(
            "⚙️ الإعدادات:\n"
            f"- اللغة: {u['lang']}\n"
            f"- المخاطرة: {u['risk']}\n"
            f"- Auto (Paper): {'ON' if u['auto'] else 'OFF'}\n"
            f"- Watchlist: {', '.join(u['watch'])}\n"
            "استخدم: /lang /risk /watch /auto"
        )
    else:
        await update.message.reply_text(
            "⚙️ Settings:\n"
            f"- Language: {u['lang']}\n"
            f"- Risk: {u['risk']}\n"
            f"- Auto (Paper): {'ON' if u['auto'] else 'OFF'}\n"
            f"- Watchlist: {', '.join(u['watch'])}\n"
            "Use: /lang /risk /watch /auto"
        )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    text = sanitize_text(update.message.text or "")
    if not text:
        return

    # Button mapping (one language per user mode)
    lang_for_ui = detect_lang(text, u["lang"])
    lang_tag = "ar" if lang_for_ui == "ar" else "en"

    # Map buttons to commands
    if text in ("📊 تحليل", "📊 Analysis"):
        await cmd_analysis(update, context)
        return
    if text in ("🎯 إشارة", "🎯 Signal"):
        await cmd_signal(update, context)
        return
    if text in ("🐋 حيتان", "🐋 Whales"):
        await cmd_whales(update, context)
        return
    if text in ("🔎 فرص", "🔎 Scan"):
        await cmd_scan(update, context)
        return
    if text in ("⚙️ إعدادات", "⚙️ Settings"):
        await cmd_settings(update, context)
        return
    if text in ("🤖 Auto تشغيل/إيقاف", "🤖 Auto ON/OFF"):
        # toggle
        u["auto"] = not u["auto"]
        await cmd_auto(update, context)
        return
    if text in ("🧾 Paper",):
        if lang_tag == "ar":
            await update.message.reply_text("🧾 Paper: هذا وضع تجريبي فقط (بدون تنفيذ حقيقي).")
        else:
            await update.message.reply_text("🧾 Paper: Simulation only (no real orders).")
        return
    if text in ("🧠 دردشة", "🧠 Chat"):
        if lang_tag == "ar":
            await update.message.reply_text("🧠 اكتب سؤالك الآن.")
        else:
            await update.message.reply_text("🧠 Ask your question now.")
        return

    # Otherwise => AI chat
    engine: AIEngine = context.application.bot_data["ai_engine"]

    push_history(u, "user", text)
    reply = engine.chat(text, lang_mode=u["lang"], history=u["history"])
    push_history(u, "assistant", reply)

    # keep keyboard consistent
    kb = ui_keyboard("ar" if (u["lang"] == "ar") else ("en" if u["lang"] == "en" else lang_tag))
    await update.message.reply_text(reply, reply_markup=kb)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    app = Application.builder().token(token).build()

    # AI Engine singleton
    app.bot_data["ai_engine"] = AIEngine()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("auto", cmd_auto))
    app.add_handler(CommandHandler("analysis", cmd_analysis))
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CommandHandler("whales", cmd_whales))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("settings", cmd_settings))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # IMPORTANT: This helps after restarts, but doesn't fix "two instances running"
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
