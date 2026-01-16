import os
import base64
import io

from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

from storage import get_user, update_user, init_db
from utils import detect_lang, normalize_symbol, split_watchlist
from analysis_engine import build_analysis, build_signal
from data_providers import top_crypto_movers, whale_alert_recent
from trading_engine import paper_open, paper_close, paper_status, set_auto, auto_tick, set_watchlist
from ai_engine import ask_ai

from openai import OpenAI

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

# Optional for /image
_openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

MENU = ReplyKeyboardMarkup(
    [
        ["📊 Analysis", "🎯 Signal"],
        ["🐳 Whales", "🔎 Scan فرص"],
        ["🤖 Auto ON/OFF", "📒 Paper"],
        ["⚙️ Settings", "🧠 Chat"]
    ],
    resize_keyboard=True
)

def help_text_ar():
    return (
        "🤖 Smart Trading AI Bot\n\n"
        "أوامر:\n"
        "/start\n"
        "/lang auto | ar | en\n"
        "/platform binance | bybit | okx ...\n"
        "/risk 1.0\n"
        "/an BTC | TSLA | XAU\n"
        "/signal BTC\n"
        "/scan\n"
        "/whales\n"
        "/paper_open BTC buy 100\n"
        "/paper_close BTC\n"
        "/paper_status\n"
        "/auto on | off\n"
        "/watch BTC,ETH,SOL\n"
        "/auto_run\n"
        "/image BTC (اختياري)\n\n"
        "💡 تكتب مباشرة: BTC / TSLA / XAU أو أي سؤال تداول."
    )

def help_text_en():
    return (
        "🤖 Smart Trading AI Bot\n\n"
        "Commands:\n"
        "/start\n"
        "/lang auto | ar | en\n"
        "/platform binance | bybit | okx ...\n"
        "/risk 1.0\n"
        "/an BTC | TSLA | XAU\n"
        "/signal BTC\n"
        "/scan\n"
        "/whales\n"
        "/paper_open BTC buy 100\n"
        "/paper_close BTC\n"
        "/paper_status\n"
        "/auto on | off\n"
        "/watch BTC,ETH,SOL\n"
        "/auto_run\n"
        "/image BTC (optional)\n\n"
        "💡 You can type directly: BTC / TSLA / XAU or any trading question."
    )

def get_reply_lang(u: dict, msg_text: str) -> str:
    # lang_mode: auto|ar|en
    if u["lang_mode"] == "auto":
        return detect_lang(msg_text)
    return u["lang_mode"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    uid = update.effective_user.id
    u = get_user(uid)
    lang = get_reply_lang(u, update.message.text or "")
    text = help_text_ar() if lang == "ar" else help_text_en()
    await update.message.reply_text(text, reply_markup=MENU)

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    val = (context.args[0].lower().strip() if context.args else "auto")
    if val not in ("auto", "ar", "en"):
        await update.message.reply_text("Use: /lang auto | ar | en")
        return
    update_user(uid, lang_mode=val)
    await update.message.reply_text(f"✅ lang_mode={val}", reply_markup=MENU)

async def cmd_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    val = (context.args[0].lower().strip() if context.args else "binance")
    update_user(uid, platform=val)
    await update.message.reply_text(f"✅ platform={val}", reply_markup=MENU)

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Example: /risk 1.0", reply_markup=MENU)
        return
    try:
        r = float(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid number. Example: /risk 1.0", reply_markup=MENU)
        return
    if r < 0 or r > 10:
        await update.message.reply_text("❌ Risk must be between 0 and 10", reply_markup=MENU)
        return
    update_user(uid, risk=r)
    await update.message.reply_text(f"✅ risk={r}%", reply_markup=MENU)

async def cmd_an(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    sym = normalize_symbol(context.args[0] if context.args else "BTC")
    lang = get_reply_lang(u, sym)

    await update.message.chat.send_action(ChatAction.TYPING)
    out = build_analysis(sym, lang_mode=lang)
    await update.message.reply_text(out, reply_markup=MENU)

async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    sym = normalize_symbol(context.args[0] if context.args else "BTC")
    lang = get_reply_lang(u, sym)

    await update.message.chat.send_action(ChatAction.TYPING)
    out = build_signal(sym, lang_mode=lang, risk_pct=u["risk"])
    await update.message.reply_text(out, reply_markup=MENU)

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = get_reply_lang(u, update.message.text or "")

    movers = top_crypto_movers(limit=8)
    if not movers:
        await update.message.reply_text("❌ Scan failed right now.", reply_markup=MENU)
        return

    if lang == "ar":
        lines = ["🔎 صيد فرص (Top movers على Binance):"]
        for m in movers:
            lines.append(f"- {m['symbol']}: {m['chg']:.2f}% | vol={m['vol']:.0f} | last={m['last']}")
        lines.append("\n⚠️ هذا سكرين فرص، مش ضمان ربح.")
    else:
        lines = ["🔎 Opportunity scan (Binance top movers):"]
        for m in movers:
            lines.append(f"- {m['symbol']}: {m['chg']:.2f}% | vol={m['vol']:.0f} | last={m['last']}")
        lines.append("\n⚠️ This is a scan, not a profit guarantee.")
    await update.message.reply_text("\n".join(lines), reply_markup=MENU)

async def cmd_whales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = get_reply_lang(u, update.message.text or "")

    txs = whale_alert_recent(min_usd=250000)
    if txs is None:
        await update.message.reply_text(
            ("🐳 Whale tracking needs WHALE_ALERT_KEY in Railway Variables.\n"
             "Currently: OFF.")
            if lang == "en" else
            ("🐳 تتبع الحيتان يحتاج WHALE_ALERT_KEY في Railway Variables.\n"
             "حاليًا: OFF."),
            reply_markup=MENU
        )
        return

    if txs == []:
        await update.message.reply_text(
            "🐳 No whale tx found now." if lang == "en" else "🐳 ما لقيتش معاملات كبيرة توا.",
            reply_markup=MENU
        )
        return

    if lang == "ar":
        lines = ["🐳 آخر معاملات كبيرة (Whale Alert):"]
        for t in txs:
            sym = (t.get("symbol") or "").upper()
            amount = t.get("amount_usd")
            frm = t.get("from", {}).get("owner_type")
            to = t.get("to", {}).get("owner_type")
            lines.append(f"- {sym} ~{amount}$ | from={frm} -> to={to}")
    else:
        lines = ["🐳 Recent large transactions (Whale Alert):"]
        for t in txs:
            sym = (t.get("symbol") or "").upper()
            amount = t.get("amount_usd")
            frm = t.get("from", {}).get("owner_type")
            to = t.get("to", {}).get("owner_type")
            lines.append(f"- {sym} ~{amount}$ | from={frm} -> to={to}")

    await update.message.reply_text("\n".join(lines), reply_markup=MENU)

async def cmd_paper_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) < 3:
        await update.message.reply_text("Example: /paper_open BTC buy 100", reply_markup=MENU)
        return
    sym = normalize_symbol(context.args[0])
    side = context.args[1]
    try:
        usd = float(context.args[2])
    except:
        await update.message.reply_text("❌ usd must be a number", reply_markup=MENU)
        return
    msg = paper_open(uid, sym, side, usd)
    await update.message.reply_text(msg, reply_markup=MENU)

async def cmd_paper_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sym = normalize_symbol(context.args[0] if context.args else "")
    if not sym:
        await update.message.reply_text("Example: /paper_close BTC", reply_markup=MENU)
        return
    msg = paper_close(uid, sym)
    await update.message.reply_text(msg, reply_markup=MENU)

async def cmd_paper_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(paper_status(uid), reply_markup=MENU)

async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    arg = (context.args[0].lower().strip() if context.args else "")
    if arg not in ("on", "off"):
        await update.message.reply_text("Use: /auto on أو /auto off", reply_markup=MENU)
        return
    set_auto(uid, enabled=(arg == "on"))
    await update.message.reply_text(f"✅ auto={arg} (Paper)", reply_markup=MENU)

async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Example: /watch BTC,ETH,SOL", reply_markup=MENU)
        return
    w = " ".join(context.args).strip()
    set_watchlist(uid, w)
    await update.message.reply_text(f"✅ watchlist={w}", reply_markup=MENU)

async def cmd_auto_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = get_reply_lang(u, update.message.text or "")
    if u["auto_enabled"] != 1:
        await update.message.reply_text(
            "Auto is OFF. Use /auto on" if lang == "en" else "Auto OFF. استعمل /auto on",
            reply_markup=MENU
        )
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    msg = auto_tick(uid)
    await update.message.reply_text(msg, reply_markup=MENU)

async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # optional: generate AI image about analysis
    uid = update.effective_user.id
    u = get_user(uid)
    lang = get_reply_lang(u, update.message.text or "")
    topic = " ".join(context.args).strip() if context.args else "BTC"
    prompt = (
        f"Professional financial infographic about {topic} market analysis, clean style, no logos, no brand names."
    )
    try:
        await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
        img = _openai_client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )
        # some SDKs return b64_json, others url. handle both.
        data = img.data[0]
        if hasattr(data, "b64_json") and data.b64_json:
            raw = base64.b64decode(data.b64_json)
            bio = io.BytesIO(raw)
            bio.name = "image.png"
            await update.message.reply_photo(photo=bio, caption=("📷 AI image" if lang == "en" else "📷 صورة AI"), reply_markup=MENU)
        elif hasattr(data, "url") and data.url:
            await update.message.reply_photo(photo=data.url, caption=("📷 AI image" if lang == "en" else "📷 صورة AI"), reply_markup=MENU)
        else:
            await update.message.reply_text("❌ image response unsupported", reply_markup=MENU)
    except Exception as e:
        await update.message.reply_text(f"❌ Image failed: {e}", reply_markup=MENU)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    text = (update.message.text or "").strip()
    lang = get_reply_lang(u, text)

    # UX: أزرار menu
    if text in ("📊 Analysis", "📊 تحليل"):
        await update.message.reply_text("Send: BTC / TSLA / XAU  (or use /an BTC)", reply_markup=MENU)
        return
    if text in ("🎯 Signal", "🎯 إشارة"):
        await update.message.reply_text("Send: BTC / ETH ... (or use /signal BTC)", reply_markup=MENU)
        return
    if text in ("🐳 Whales", "📈 تتبع الحيتان"):
        await cmd_whales(update, context)
        return
    if text in ("🔎 Scan فرص", "🔎 Scan", "🐳 صيد فرص"):
        await cmd_scan(update, context)
        return
    if text in ("📒 Paper",):
        await update.message.reply_text("Use: /paper_open BTC buy 100 | /paper_status", reply_markup=MENU)
        return
    if text in ("🤖 Auto ON/OFF", "🤖 تداول آلي"):
        await update.message.reply_text("Use: /auto on أو /auto off ثم /auto_run", reply_markup=MENU)
        return
    if text in ("⚙️ Settings", "⚙️ إعدادات"):
        await update.message.reply_text("Use: /lang /risk /platform /watch", reply_markup=MENU)
        return
    if text in ("🧠 Chat", "🧠 دردشة"):
        await update.message.reply_text("Ask any trading question now.", reply_markup=MENU)
        return

    # لو كتب رمز أصل فقط => تحليل
    if text.isalpha() and 2 <= len(text) <= 8:
        sym = normalize_symbol(text)
        await update.message.chat.send_action(ChatAction.TYPING)
        out = build_analysis(sym, lang_mode=lang)
        await update.message.reply_text(out, reply_markup=MENU)
        return

    # غير ذلك => ChatGPT تداول (بنفس لغة المستخدم فقط)
    await update.message.chat.send_action(ChatAction.TYPING)
    extra = f"User settings: platform={u['platform']} risk={u['risk']}% watchlist={u['watchlist']}"
    ans = ask_ai(text, lang_mode=lang, extra_context=extra)
    await update.message.reply_text(ans, reply_markup=MENU)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("platform", cmd_platform))
    app.add_handler(CommandHandler("risk", cmd_risk))

    app.add_handler(CommandHandler("an", cmd_an))
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("whales", cmd_whales))

    app.add_handler(CommandHandler("paper_open", cmd_paper_open))
    app.add_handler(CommandHandler("paper_close", cmd_paper_close))
    app.add_handler(CommandHandler("paper_status", cmd_paper_status))

    app.add_handler(CommandHandler("auto", cmd_auto))
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("auto_run", cmd_auto_run))

    app.add_handler(CommandHandler("image", cmd_image))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("BOT FILE LOADED")
    print("RUNNING POLLING")
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
