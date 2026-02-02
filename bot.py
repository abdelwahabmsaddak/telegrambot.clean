import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ======================
# تحميل المتغيرات
# ======================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN غير موجود")

# ======================
# Handlers
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📊 تحليل", callback_data="analysis"),
            InlineKeyboardButton("🎯 إشارة", callback_data="signal"),
        ],
        [
            InlineKeyboardButton("🤖 Auto Paper", callback_data="paper"),
            InlineKeyboardButton("⚡ Auto Live", callback_data="live"),
        ],
        [
            InlineKeyboardButton("🧠 دردشة", callback_data="chat"),
            InlineKeyboardButton("⚙️ إعدادات", callback_data="settings"),
        ],
    ]

    await update.message.reply_text(
        "🤖 أهلاً بك في البوت الذكي\nاختر من القائمة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "analysis":
        await query.edit_message_text("📊 تحليل السوق (تجريبي)")

    elif data == "signal":
        await query.edit_message_text("🎯 إشارة تداول (تجريبية)")

    elif data == "paper":
        await query.edit_message_text("🤖 Auto Paper Trading مفعّل")

    elif data == "live":
        await query.edit_message_text("⚡ Auto Live Trading (بدون تنفيذ حقيقي)")

    elif data == "chat":
        await query.edit_message_text("🧠 دردشة ذكاء اصطناعي (لاحقاً)")

    elif data == "settings":
        await query.edit_message_text("⚙️ الإعدادات")

# ======================
# Main
# ======================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 البوت يعمل ...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
