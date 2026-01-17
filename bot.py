import os
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from ai_engine import ai_chat

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    await update.message.chat.send_action("typing")

    try:
        reply = ai_chat(user_text)
    except Exception as e:
        reply = "❌ حصل خطأ في الذكاء الاصطناعي. حاول لاحقًا."

    await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 AI CHAT BOT RUNNING")
    app.run_polling()

if __name__ == "__main__":
    main()
