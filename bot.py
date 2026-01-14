import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from core.ai_engine import chat_answer
from core.market_data import get_crypto_price, get_stock_price, get_gold_price
from core.storage import get_user, set_user, init_db

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        "👋 مرحبا / Hi!\n"
        "أنا بوت تحليل وتداول.\n\n"
        "أوامر:\n"
        "/lang ar | en | auto\n"
        "/platform binance | bybit | okx | kucoin ...\n"
        "/risk 1.0  (نسبة المخاطرة %)\n"
        "/an BTC  أو  /an stock TSLA  أو  /an gold\n"
        "/chat سؤالك\n"
    )

async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = (context.args[0].lower() if context.args else "auto")
    if val not in ["ar", "en", "auto"]:
        await update.message.reply_text("استعمل: /lang ar أو /lang en أو /lang auto")
        return
    set_user(update.effective_user.id, lang=val)
    await update.message.reply_text(f"✅ تم ضبط اللغة: {val}")

async def platform_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = (context.args[0].lower() if context.args else "binance")
    set_user(update.effective_user.id, platform=val)
    await update.message.reply_text(f"✅ تم اختيار المنصة: {val}")

async def risk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = float(context.args[0])
        if r <= 0 or r > 10:
            raise ValueError()
    except Exception:
        await update.message.reply_text("اكتب: /risk 1.0  (بين 0 و 10)")
        return
    set_user(update.effective_user.id, risk=r)
    await update.message.reply_text(f"✅ تم ضبط المخاطرة: {r}%")

async def chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("اكتب سؤالك بعد /chat")
        return
    u = get_user(update.effective_user.id)
    ans = chat_answer(text, lang=u["lang"])
    await update.message.reply_text(ans)

async def an_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال: /an BTC  أو  /an stock TSLA  أو  /an gold")
        return

    u = get_user(update.effective_user.id)
    a0 = context.args[0].lower()

    if a0 == "gold":
        price = get_gold_price()
        if price is None:
            await update.message.reply_text("🟡 الذهب: مزوّد السعر قيد الإضافة في V1.1 ✅")
            return
        await update.message.reply_text(f"🟡 Gold price: {price}")
        return

    if a0 == "stock" and len(context.args) >= 2:
        sym = context.args[1].upper()
        p = get_stock_price(sym)
        if p is None:
            await update.message.reply_text("❌ ما لقيتش السعر. جرّب رمز آخر.")
            return
        prompt = f"حلل سهم {sym} بسعر تقريبي {p}. أعطني دعم/مقاومة وسيناريوهات ومخاطر."
        ans = chat_answer(prompt, lang=u["lang"])
        await update.message.reply_text(f"📈 {sym} ~ {p}\n\n{ans}")
        return

    # crypto
    sym = context.args[0].upper()
    p = get_crypto_price(sym)
    if p is None:
        await update.message.reply_text("❌ ما لقيتش السعر. جرّب رمز: BTC ETH SOL ...")
        return
    prompt = f"حلل {sym} بسعر تقريبي {p}. أعطني مستويات مهمة وسيناريوهات وإدارة مخاطرة."
    ans = chat_answer(prompt, lang=u["lang"])
    await update.message.reply_text(f"🪙 {sym} ~ {p}\n\n{ans}")

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اكتب /start لرؤية الأوامر. أو استعمل /chat سؤالك.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CommandHandler("platform", platform_cmd))
    app.add_handler(CommandHandler("risk", risk_cmd))
    app.add_handler(CommandHandler("chat", chat_cmd))
    app.add_handler(CommandHandler("an", an_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    print("RUNNING POLLING")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
