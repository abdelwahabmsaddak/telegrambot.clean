import os
import logging
from chart_engine import generate_chart
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# =======================
# ENV
# =======================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN missing")

if not OPENAI_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY missing")

# =======================
# OPENAI CLIENT
# =======================
client = OpenAI(api_key=OPENAI_KEY)

# =======================
# LOGGING
# =======================
logging.basicConfig(level=logging.INFO)

# =======================
# KEYBOARD
# =======================
MAIN_KB = ReplyKeyboardMarkup(
    [
        ["📊 Analysis", "🎯 Signal"],
        ["🐋 Whales", "💬 Chat"],
        ["⚙️ Settings"],
    ],
    resize_keyboard=True
)

# =======================
# HELPERS
# =======================
def detect_lang(text: str) -> str:
    for ch in text:
        if "\u0600" <= ch <= "\u06FF":
            return "ar"
    return "en"

def ai_answer(prompt: str, lang: str) -> str:
    system_prompt = (
        "أنت مساعد تداول محترف. "
        "تقدم تحليلات تعليمية فقط بدون أوامر تداول حقيقية."
        if lang == "ar"
        else
        "You are a professional trading assistant. "
        "Provide educational analysis only, no real trade execution."
    )

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=700,
    )

    return response.choices[0].message.content.strip()

# =======================
# COMMANDS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Smart Trading Bot\n"
        "AI Analysis • Signals • Chat\n"
        "اختر من القائمة 👇",
        reply_markup=MAIN_KB
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start تشغيل\n"
        "/help مساعدة\n"
        "أو استخدم الأزرار"
    )

# =======================
# TEXT HANDLER
# =======================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lang = detect_lang(text)

    try:
        # -------- ANALYSIS --------
        if text in ["📊 Analysis", "تحليل"]:
            msg = (
                "📊 أرسل الرمز:\nBTC / ETH / TSLA / XAUUSD"
                if lang == "ar"
                else
                "📊 Send symbol:\nBTC / ETH / TSLA / XAUUSD"
            )
            await update.message.reply_text(msg)
            return

        # -------- SIGNAL --------
        if text in ["🎯 Signal", "إشارة"]:
            prompt = (
                "اعطني مثال إشارة تداول تعليمية مع إدارة مخاطر."
                if lang == "ar"
                else
                "Give an educational trading signal example with risk management."
            )
            await update.message.reply_text(ai_answer(prompt, lang))
            return

        # -------- WHALES --------
        if text in ["🐋 Whales", "حيتان"]:
            msg = (
                "🐋 تتبع الحيتان سيتم ربطه بـ API لاحقًا."
                if lang == "ar"
                else
                "🐋 Whale tracking will be added via API later."
            )
            await update.message.reply_text(msg)
            return

        # -------- CHAT --------
        if text in ["💬 Chat", "دردشة"]:
            msg = (
                "💬 وضع الدردشة مفعل. اسأل أي شيء."
                if lang == "ar"
                else
                "💬 Chat mode enabled. Ask anything."
            )
            await update.message.reply_text(msg)
            return

        # -------- SETTINGS --------
        if text in ["⚙️ Settings", "إعدادات"]:
            msg = (
                "⚙️ الإعدادات ستضاف لاحقًا."
                if lang == "ar"
                else
                "⚙️ Settings coming soon."
            )
            await update.message.reply_text(msg)
            return

        # -------- AI DEFAULT --------
        await update.message.reply_text(ai_answer(text, lang))

    except Exception as e:
        await update.message.reply_text(
            "❌ AI Error. Try again later."
            if lang == "en"
            else
            "❌ حصل خطأ في الذكاء الاصطناعي."
        )
        logging.error(e)

# =======================
# MAIN
# =======================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 AI BOT RUNNING...")
    app.run_polling()

# =======================
# RUN
# =======================
if __name__ == "__main__":
    main()
