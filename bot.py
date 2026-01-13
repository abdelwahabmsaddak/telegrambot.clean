from telegram.ext import Application, CommandHandler
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update, context):
    await update.message.reply_text("✅ البوت يخدم توّا")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

print("Bot is running...")
app.run_polling(drop_pending_updates=True)
