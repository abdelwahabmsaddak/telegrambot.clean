import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var")

app = FastAPI()
tg_app = Application.builder().token(BOT_TOKEN).build()


# -------- Handlers --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبا 👋\n"
        "اكتب:\n"
        "price\nhelp\ncontact"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()

    if text == "price":
        await update.message.reply_text("🇹🇳 تونس: 40 دينار/شهر\n🌍 الخليج: 15$/شهر")
    elif text == "help":
        await update.message.reply_text("اكتب: price أو contact")
    elif text == "contact":
        await update.message.reply_text("📩 تواصل: @yourusername")
    else:
        await update.message.reply_text("❌ سؤال غير مدعوم. اكتب help.")

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


# -------- FastAPI lifecycle (المهمّة اللي ناقصة) --------
@app.on_event("startup")
async def on_startup():
    await tg_app.initialize()
    await tg_app.start()

@app.on_event("shutdown")
async def on_shutdown():
    await tg_app.stop()
    await tg_app.shutdown()


# -------- Routes --------
@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
