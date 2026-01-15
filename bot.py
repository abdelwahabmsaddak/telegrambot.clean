import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from ai_engine import smart_reply
from analysis import analyze_asset

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 مرحبا!\n\n"
        "أنا SmartBot 🤖\n"
        "أحلل العملات، الأسهم، والذهب.\n\n"
        "✍️ اكتب مثلا:\n"
        "- BTC\n"
        "- حلل BTC\n"
        "- XAU\n"
        "- TSLA\n"
        "- سؤال حر عن التداول"
    )
    await update.message.reply_text(text)

# ===== Messages =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    # إذا ذكر أصل معروف
    asset = extract_asset(user_text)

    if asset:
        result = analyze_asset(asset)
        await update.message.reply_text(result)
    else:
        # Chat ذكي
        reply = smart_reply(user_text)
        await update.message.reply_text(reply)

def extract_asset(text: str):
    text = text.upper()
    for a in ["BTC", "ETH", "XAU", "GOLD", "TSLA"]:
        if a in text:
            return "XAU" if a == "GOLD" else a
    return None

# ===== Run =====
def main():
    print("BOT FILE LOADED")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("RUNNING POLLING")
    app.run_polling()

if __name__ == "__main__":
    main()
