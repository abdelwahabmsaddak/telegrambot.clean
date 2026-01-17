import os
import re
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# ================== ENV ==================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

# ================== UTILS ==================
def clean_text(text: str) -> str:
    if not text:
        return ""
    # remove hidden RTL/LTR chars
    text = text.replace("\u200e", "").replace("\u200f", "")
    return text.strip()

def detect_lang(text: str) -> str:
    # Arabic detection
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    return "en"

# ================== AI ==================
def ai_reply(message: str) -> str:
    message = clean_text(message)
    lang = detect_lang(message)

    system_prompt = (
        "أنت مساعد تداول ذكي ومحترف." if lang == "ar"
        else "You are a professional AI trading assistant."
    )

    rules = (
        "جاوب بنفس لغة المستخدم فقط. "
        "قدّم تحليل، إدارة مخاطر، شرح، بدون تنفيذ صفقات حقيقية."
        if lang == "ar"
        else
        "Reply in the same language only. "
        "Provide analysis, risk management, explanations. No real trades."
    )

    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt + " " + rules},
                {"role": "user", "content": message},
            ],
            temperature=0.7,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ AI Error: {e}"

# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Smart Trading AI Bot\n\n"
        "اكتب أي سؤال في التداول (عملات رقمية، أسهم، ذهب)\n"
        "أو أي سؤال عام، وسأجيبك بالذكاء الاصطناعي.\n\n"
        "🧠 AI Ready ✅"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start – تشغيل البوت\n"
        "/help – مساعدة\n\n"
        "✍️ فقط اكتب سؤالك مباشرة."
    )

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = clean_text(update.message.text)

    if not user_text:
        return

    reply = ai_reply(user_text)
    await update.message.reply_text(reply)

# ================== MAIN ==================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ TELEGRAM_BOT_TOKEN غير موجود")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("🤖 AI BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
