import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from router import route_message

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

MENU = ReplyKeyboardMarkup(
    [
        ["📊 تحليل", "🎯 إشارة"],
        ["🐳 صيد فرص", "🧠 اسألني"],
        ["🤖 تداول آلي", "⚙️ إعدادات"]
    ],
    resize_keyboard=True
)

async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Smart Trading Bot\n\nاختر من القائمة أو اكتب سؤالك مباشرة:",
        reply_markup=MENU
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    reply = route_message(user_text)
    await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle))
    app.add_handler(MessageHandler(filters.ALL, entry))
    app.run_polling()

if __name__ == "__main__":
    main()
