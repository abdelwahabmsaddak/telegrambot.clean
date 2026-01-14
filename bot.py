    import os
import re
import json
import asyncio
from datetime import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

from ai_engine import chat_answer, detect_lang_auto
from market_data import (
    get_crypto_quote, get_stock_quote, get_gold_quote,
    normalize_symbol_guess, quick_market_snapshot
)
from trading import (
    set_user, get_user, reset_user,
    build_trade_idea, paper_trade_open, paper_trade_close, paper_trade_status
)
from charting import build_price_chart_png

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var")

def _help_text():
    return (
        "🤖 SmartBot — أوامر أساسية:\n\n"
        "/start — تعليمات سريعة\n"
        "/lang auto|ar|en — لغة الرد\n"
        "/platform binance|bybit|okx|kucoin|... — اختيار منصة\n"
        "/risk 0.5 — ضبط المخاطرة % (0 إلى 10)\n"
        "/an BTC — تحليل أصل (BTC/ETH/TSLA/XAU)\n"
        "/chart BTC — رسم شارت PNG\n"
        "/signal BTC — فكرة صفقة مع إدارة مخاطر\n"
        "/paper_open BTC buy 100 — فتح Paper Trade\n"
        "/paper_close BTC — غلق\n"
        "/paper_status — عرض صفقات Paper\n"
        "/reset — تصفير الإعدادات\n\n"
        "💡 تقدر تكتب مباشرة:\n"
        "- رقم وحده (مثلاً 2) → يتسجل Risk\n"
        "- BTC أو TSLA → تحليل سريع\n"
        "- أي سؤال → Chat AI\n"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    msg = (
        "✅ البوت شغال.\n\n"
        f"⚙️ إعداداتك الحالية:\n"
        f"- اللغة: {u['lang']}\n"
        f"- المنصة: {u['platform']}\n"
        f"- Risk: {u['risk']}%\n\n"
        + _help_text()
    )
    await update.message.reply_text(msg)

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("استعمل: /lang auto أو /lang ar أو /lang en")
        return
    val = context.args[0].lower().strip()
    if val not in ("auto", "ar", "en"):
        await update.message.reply_text("القيم: auto | ar | en")
        return
    set_user(uid, lang=val)
    await update.message.reply_text(f"✅ تم ضبط اللغة: {val}")

async def cmd_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("استعمل: /platform binance أو bybit أو okx ...")
        return
    val = context.args[0].lower().strip()
    set_user(uid, platform=val)
    await update.message.reply_text(f"✅ تم اختيار المنصة: {val}")

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("اكتب: /risk 2  (بين 0 و 10)")
        return
    try:
        r = float(context.args[0])
    except:
        await update.message.reply_text("❌ رقم غير صحيح. مثال: /risk 1.5")
        return
    if r < 0 or r > 10:
        await update.message.reply_text("❌ لازم بين 0 و 10")
        return
    set_user(uid, risk=r)
    await update.message.reply_text(f"✅ تم ضبط المخاطرة: {r}%")

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_user(update.effective_user.id)
    await update.message.reply_text("✅ تم تصفير الإعدادات. اكتب /start")

async def cmd_an(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    if not context.args:
        await update.message.reply_text("استعمل: /an BTC أو /an TSLA أو /an XAU")
        return
    sym_raw = context.args[0].strip().upper()
    sym = normalize_symbol_guess(sym_raw)

    await update.message.chat.send_action(ChatAction.TYPING)

    snap = quick_market_snapshot(sym)
    prompt = (
        f"اعطني تحليل احترافي للأصل {sym}.\n"
        f"بيانات سريعة:\n{snap}\n\n"
        f"مطلوب:\n"
        f"- نظرة عامة\n- اتجاه محتمل (قصير/متوسط)\n"
        f"- مستويات دعم/مقاومة تقريبية\n"
        f"- خطة مخاطرة مناسبة لمستخدم Risk={u['risk']}%\n"
        f"- تنبيه مخاطر واضح\n"
        f"اكتب بالعربية إذا كان المستخدم عربي وإلا بالإنجليزية."
    )
    ans = chat_answer(prompt, lang=u["lang"])
    await update.message.reply_text(ans)

async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استعمل: /chart BTC أو /chart TSLA أو /chart XAU")
        return
    sym = normalize_symbol_guess(context.args[0].strip().upper())
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)

    png_path, caption = build_price_chart_png(sym)
    if not png_path:
        await update.message.reply_text("❌ ما قدرتش نجيب بيانات الشارت حالياً.")
        return

    with open(png_path, "rb") as f:
        await update.message.reply_photo(photo=f, caption=caption)

async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    if not context.args:
        await update.message.reply_text("استعمل: /signal BTC")
        return
    sym = normalize_symbol_guess(context.args[0].strip().upper())
    await update.message.chat.send_action(ChatAction.TYPING)

    idea = build_trade_idea(sym, risk_pct=u["risk"], platform=u["platform"])
    # idea نص جاهز + توصيات مخاطرة بدون تنفيذ
    await update.message.reply_text(idea)

async def cmd_paper_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) < 3:
        await update.message.reply_text("استعمل: /paper_open BTC buy 100")
        return
    sym = normalize_symbol_guess(context.args[0].upper())
    side = context.args[1].lower()
    try:
        usd = float(context.args[2])
    except:
        await update.message.reply_text("❌ المبلغ لازم رقم. مثال: 100")
        return

    res = paper_trade_open(uid, sym, side, usd)
    await update.message.reply_text(res)

async def cmd_paper_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("استعمل: /paper_close BTC")
        return
    sym = normalize_symbol_guess(context.args[0].upper())
    res = paper_trade_close(uid, sym)
    await update.message.reply_text(res)

async def cmd_paper_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(paper_trade_status(uid))

# ---------- UX ذكي: يلتقط رسائل بدون أوامر ----------
NUM_ONLY_RE = re.compile(r"^\s*\d+(\.\d+)?\s*$")
SYMBOL_RE = re.compile(r"^\s*[A-Za-z]{2,6}\s*$")

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    text = (update.message.text or "").strip()

    # 1) رقم فقط => Risk
    if NUM_ONLY_RE.match(text):
        r = float(text)
        if 0 <= r <= 10:
            set_user(uid, risk=r)
            await update.message.reply_text(f"✅ Risk تم ضبطه: {r}%\nاكتب BTC للتحليل أو اسأل سؤال.")
            return

    # 2) رمز مختصر => تحليل سريع
    if SYMBOL_RE.match(text):
        sym = normalize_symbol_guess(text.upper())
        await update.message.chat.send_action(ChatAction.TYPING)

        snap = quick_market_snapshot(sym)
        prompt = (
            f"حلل سريع للأصل {sym} بناءً على البيانات:\n{snap}\n"
            f"أعطني نقاط مهمة + إدارة مخاطر على Risk={u['risk']}%."
        )
        ans = chat_answer(prompt, lang=u["lang"])
        await update.message.reply_text(ans)
        return

    # 3) سؤال عام => Chat AI
    await update.message.chat.send_action(ChatAction.TYPING)
    # Auto language detection if user set auto
    if u["lang"] == "auto":
        detected = detect_lang_auto(text)
    else:
        detected = u["lang"]

    prompt = (
        "أنت مساعد تداول محترف. جاوب بشكل واضح وعملي.\n"
        "ممنوع تعطي وعود أرباح. وضّح المخاطر.\n"
        "إذا طلب تنفيذ تداول حقيقي، اقترح Paper Trading أولاً.\n\n"
        f"سؤال المستخدم: {text}\n"
    )
    ans = chat_answer(prompt, lang=detected)
    await update.message.reply_text(ans)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("platform", cmd_platform))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("reset", cmd_reset))

    app.add_handler(CommandHandler("an", cmd_an))
    app.add_handler(CommandHandler("chart", cmd_chart))
    app.add_handler(CommandHandler("signal", cmd_signal))

    app.add_handler(CommandHandler("paper_open", cmd_paper_open))
    app.add_handler(CommandHandler("paper_close", cmd_paper_close))
    app.add_handler(CommandHandler("paper_status", cmd_paper_status))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    print("BOT FILE LOADED")
    print("RUNNING POLLING")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
