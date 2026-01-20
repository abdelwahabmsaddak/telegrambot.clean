# bot.py
import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from ai_engine import ai_chat, sanitize_text

# --- Logging (UTF-8 safe) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("smartbot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var")

# Simple in-memory user settings
_USERS = {}

DEFAULTS = {
    "lang": "auto",   # auto / ar / en
    "mode": "chat",   # chat / analysis / signal
}

def get_user(uid: int):
    u = _USERS.get(uid)
    if not u:
        u = dict(DEFAULTS)
        _USERS[uid] = u
    return u

def detect_lang(text: str) -> str:
    # If user forced lang, we ignore detect. This is for auto mode.
    # Arabic range detection:
    for ch in text:
        if "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F":
            return "ar"
    return "en"

def main_keyboard(lang: str):
    # Keep UI in user's language ONLY
    if lang == "ar":
        return ReplyKeyboardMarkup(
            [
                ["📊 تحليل", "🎯 إشارة"],
                ["🧠 دردشة", "⚙️ إعدادات"],
                ["🌐 لغة: عربي", "🌐 Language: English"],
            ],
            resize_keyboard=True
        )
    return ReplyKeyboardMarkup(
        [
            ["📊 Analysis", "🎯 Signal"],
            ["🧠 Chat", "⚙️ Settings"],
            ["🌐 Arabic", "🌐 English"],
        ],
        resize_keyboard=True
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    # default language: auto; show bilingual small intro
    txt = (
        "✅ أهلاً! اختر من الأزرار.\n"
        "—\n"
        "✅ Welcome! Use the buttons."
    )
    await update.message.reply_text(txt)

    # show keyboard in Arabic by default (you can switch)
    await update.message.reply_text(
        "اختر:" if True else "Choose:",
        reply_markup=main_keyboard("ar")
    )

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    arg = (context.args[0].lower() if context.args else "").strip()
    if arg in ("ar", "arabic", "عربي", "العربية"):
        u["lang"] = "ar"
        await update.message.reply_text("✅ تم ضبط اللغة: العربية", reply_markup=main_keyboard("ar"))
    elif arg in ("en", "english", "انجليزي", "english"):
        u["lang"] = "en"
        await update.message.reply_text("✅ Language set: English", reply_markup=main_keyboard("en"))
    else:
        u["lang"] = "auto"
        await update.message.reply_text("✅ lang_mode=auto (يحددها حسب رسالتك)")

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    arg = (context.args[0].lower() if context.args else "").strip()
    if arg in ("chat", "analysis", "signal"):
        u["mode"] = arg
        await update.message.reply_text(f"✅ mode={arg}")
    else:
        await update.message.reply_text("Use: /mode chat | /mode analysis | /mode signal")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "الأوامر:\n"
        "/start\n"
        "/lang ar | /lang en | /lang auto\n"
        "/mode chat | analysis | signal\n"
        "\n"
        "You can also just type your question.\n"
    )
    await update.message.reply_text(txt)

def build_prompt(mode: str, text: str, lang: str) -> str:
    text = sanitize_text(text)
    if lang == "ar":
        if mode == "analysis":
            return f"حلّل هذا الرمز أو السؤال باحتراف: {text}\nقدّم سيناريوهين + إدارة مخاطرة."
        if mode == "signal":
            return f"أعطني فكرة تداول تعليمية (دخول/وقف/أهداف) لهذا: {text}\nمع تحذير مخاطرة."
        return text  # chat
    else:
        if mode == "analysis":
            return f"Provide a professional analysis for: {text}. Include 2 scenarios + risk management."
        if mode == "signal":
            return f"Give an educational trade idea (entry/stop/targets) for: {text}. Include risk warning."
        return text

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    incoming = sanitize_text(update.message.text or "")
    if not incoming:
        return

    # Buttons (Arabic)
    if incoming in ("📊 تحليل", "🎯 إشارة", "🧠 دردشة", "⚙️ إعدادات", "🌐 لغة: عربي", "🌐 Language: English"):
        if incoming == "📊 تحليل":
            u["mode"] = "analysis"
            await update.message.reply_text("✅ وضع التحليل. أرسل الرمز مثل: BTC أو TSLA أو XAUUSD")
            return
        if incoming == "🎯 إشارة":
            u["mode"] = "signal"
            await update.message.reply_text("✅ وضع الإشارة (تعليمي). أرسل الرمز مثل: BTC")
            return
        if incoming == "🧠 دردشة":
            u["mode"] = "chat"
            await update.message.reply_text("✅ وضع الدردشة. اسألني أي سؤال.")
            return
        if incoming == "⚙️ إعدادات":
            await update.message.reply_text("Use: /lang ar | /lang en | /lang auto\nUse: /mode chat|analysis|signal")
            return
        if incoming == "🌐 لغة: عربي":
            u["lang"] = "ar"
            await update.message.reply_text("✅ تم ضبط اللغة: العربية", reply_markup=main_keyboard("ar"))
            return
        if incoming == "🌐 Language: English":
            u["lang"] = "en"
            await update.message.reply_text("✅ Language set: English", reply_markup=main_keyboard("en"))
            return

    # Buttons (English)
    if incoming in ("📊 Analysis", "🎯 Signal", "🧠 Chat", "⚙️ Settings", "🌐 Arabic", "🌐 English"):
        if incoming == "📊 Analysis":
            u["mode"] = "analysis"
            await update.message.reply_text("✅ Analysis mode. Send a symbol like BTC / TSLA / XAUUSD")
            return
        if incoming == "🎯 Signal":
            u["mode"] = "signal"
            await update.message.reply_text("✅ Signal mode (educational). Send a symbol like BTC")
            return
        if incoming == "🧠 Chat":
            u["mode"] = "chat"
            await update.message.reply_text("✅ Chat mode. Ask anything.")
            return
        if incoming == "⚙️ Settings":
            await update.message.reply_text("Use: /lang ar|en|auto  |  /mode chat|analysis|signal")
            return
        if incoming == "🌐 Arabic":
            u["lang"] = "ar"
            await update.message.reply_text("✅ تم ضبط اللغة: العربية", reply_markup=main_keyboard("ar"))
            return
        if incoming == "🌐 English":
            u["lang"] = "en"
            await update.message.reply_text("✅ Language set: English", reply_markup=main_keyboard("en"))
            return

    # Choose language
    lang = u["lang"]
    if lang == "auto":
        lang = detect_lang(incoming)

    prompt = build_prompt(u["mode"], incoming, lang)

    try:
        answer = ai_chat(prompt, lang=lang)
        await update.message.reply_text(answer)
    except Exception as e:
        # Log full error, but send short safe message to user (no weird chars)
        log.exception("AI failure: %s", repr(e))
        if lang == "ar":
            await update.message.reply_text("❌ حصل خطأ في الذكاء الاصطناعي. تأكد من OPENAI_API_KEY ثم جرّب لاحقًا.")
        else:
            await update.message.reply_text("❌ AI error. Check OPENAI_API_KEY and try again.")

def build_app():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("mode", cmd_mode))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app

if __name__ == "__main__":
    # IMPORTANT: Railway must run ONLY ONE instance
    app = build_app()
    log.info("AI BOT RUNNING...")
    app.run_polling(close_loop=False)
