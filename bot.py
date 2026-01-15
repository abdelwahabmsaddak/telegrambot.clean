import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from router import route_message

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["📊 تحليل أصل", "🎯 إشارة تداول"],
        ["🧠 دردشة ذكية", "📈 تتبع الحيتان"],
        ["🤖 تداول آلي", "⚙️ الإعدادات"]
    ],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 مرحبا بك في Smart Trading Bot\n\nاختر من القائمة 👇",
        reply_markup=MAIN_MENU
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    response = route_message(user_text)
    await update.message.reply_text(response)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
