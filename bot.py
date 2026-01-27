import os
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

from engine import analyze, format_signal, scan, paper_open, paper_status
from services import whale_alert_latest, ai_chat
from storage import set_user, get_user

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("smartbot")

def env_token() -> str:
    # يدعم الاسمين
    t = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not t:
        t = os.getenv("TELEGRAM_TOKEN", "").strip()
    return t

DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "bybit").strip()
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "15m").strip()
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "200").strip())
SCAN_TOP = int(os.getenv("SCAN_TOP", "15").strip())
SCAN_TIMEFRAME = os.getenv("SCAN_TIMEFRAME", DEFAULT_TIMEFRAME).strip()
SCAN_LIMIT = int(os.getenv("SCAN_LIMIT", str(DEFAULT_LIMIT)).strip())

ALLOW_LIVE = os.getenv("ALLOW_LIVE", "false").strip().lower() == "true"

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تحليل", callback_data="ANALYZE"),
         InlineKeyboardButton("🎯 إشارة", callback_data="SIGNAL")],
        [InlineKeyboardButton("🧾 Scan", callback_data="SCAN"),
         InlineKeyboardButton("🤖 Chat", callback_data="CHAT")],
        [InlineKeyboardButton("🧪 Auto Paper", callback_data="PAPER"),
         InlineKeyboardButton("🐋 Whales", callback_data="WHALES")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ SmartBot جاهز. اختر من القائمة:", reply_markup=main_menu())

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data in ("ANALYZE", "SIGNAL"):
        set_user(uid, {"mode": q.data, "await": "symbol"})
        await q.edit_message_text("✍️ ابعث الرمز (مثال: BTC أو BTC/USDT) + (اختياري) timeframe مثل 15m\nمثال: BTC 15m")
        return

    if q.data == "SCAN":
        await q.edit_message_text("⏳ Scan شغال... ثواني")
        items = scan(DEFAULT_EXCHANGE, SCAN_TIMEFRAME, SCAN_LIMIT, top=SCAN_TOP)
        if not items:
            await q.edit_message_text("❌ ما لقيتش فرص واضحة الآن.", reply_markup=main_menu())
            return
        lines = ["🧾 أفضل فرص (Crypto/USDT):"]
        for it in items[:10]:
            lines.append(f"- {it['symbol']} | {it['side']} | RSI {it['rsi']:.1f} | RR {it['rr']:.1f}")
        lines.append("\nابعث رمز من القائمة باش نعطيك Entry/SL/TP.")
        await q.edit_message_text("\n".join(lines), reply_markup=main_menu())
        return

    if q.data == "PAPER":
        set_user(uid, {"mode": "PAPER", "await": "paper_cmd"})
        await q.edit_message_text("🧪 Paper: اكتب\n- status\nأو\n- open BTC 50  (يعني $50)\nثم نعطيك صفقة Paper تلقائياً", reply_markup=main_menu())
        return

    if q.data == "WHALES":
        key = os.getenv("WHALEALERT_API_KEY", "").strip()
        if not key:
            await q.edit_message_text("🐋 Whales يحتاج WHALEALERT_API_KEY في ENV.", reply_markup=main_menu())
            return
        txs = await whale_alert_latest(key, limit=5)
        if not txs:
            await q.edit_message_text("🐋 لا توجد معاملات كبيرة الآن.", reply_markup=main_menu())
            return
        lines = ["🐋 Whale moves:"]
        for t in txs:
            amount = t.get("amount_usd", 0)
            sym = t.get("symbol", "")
            fr = t.get("from", {}).get("owner_type", "unknown")
            to = t.get("to", {}).get("owner_type", "unknown")
            lines.append(f"- {sym} | ${amount:,.0f} | {fr} → {to}")
        await q.edit_message_text("\n".join(lines), reply_markup=main_menu())
        return

    if q.data == "CHAT":
        set_user(uid, {"mode": "CHAT", "await": "chat"})
        await q.edit_message_text("🤖 اكتب سؤالك الآن (لو OPENAI_API_KEY مش موجود، نجاوبك ردّ منطقي مختصر).", reply_markup=main_menu())
        return

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = (update.message.text or "").strip()
    st = get_user(uid)
    mode = st.get("mode")
    awaiting = st.get("await")

    if mode in ("ANALYZE", "SIGNAL") and awaiting == "symbol":
        # parse: "BTC 15m"
        parts = txt.split()
        symbol = parts[0]
        tf = parts[1] if len(parts) > 1 else DEFAULT_TIMEFRAME
        try:
            res = analyze(DEFAULT_EXCHANGE, symbol, tf, DEFAULT_LIMIT)
            out = format_signal(res)
            # لو user ضغط "إشارة" وطلعت فرصة، نعرض زر Paper Open
            kb = main_menu()
            if res.get("side"):
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Open Paper ($50)", callback_data=f"OPENPAPER|{res['symbol']}")],
                    *kb.inline_keyboard
                ])
            await update.message.reply_text(out, reply_markup=kb)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}", reply_markup=main_menu())
        return

    if mode == "PAPER" and awaiting == "paper_cmd":
        if txt.lower() == "status":
            await update.message.reply_text(paper_status(uid), reply_markup=main_menu())
            return
        if txt.lower().startswith("open"):
            # open BTC 50
            p = txt.split()
            if len(p) < 3:
                await update.message.reply_text("اكتب: open BTC 50", reply_markup=main_menu()); return
            symbol = p[1]
            usd = float(p[2])
            try:
                res = analyze(DEFAULT_EXCHANGE, symbol, DEFAULT_TIMEFRAME, DEFAULT_LIMIT)
                if not res.get("side"):
                    await update.message.reply_text("🟡 ما ثماش setup واضح للـPaper الآن.", reply_markup=main_menu()); return
                ok, msg = paper_open(uid, res["symbol"], res["side"], res["entry"], res["sl"], res["tp"], size_usd=usd)
                await update.message.reply_text(msg, reply_markup=main_menu())
            except Exception as e:
                await update.message.reply_text(f"❌ {e}", reply_markup=main_menu())
            return

    if mode == "CHAT" and awaiting == "chat":
        ans = await ai_chat(txt)
        if not ans:
            # fallback short “no-AI” answer
            ans = "اكتب: تحليل BTC 15m أو استعمل زر Scan. للـAI لازم OPENAI_API_KEY."
        await update.message.reply_text(ans, reply_markup=main_menu())
        return

    # default
    await update.message.reply_text("اختر من القائمة:", reply_markup=main_menu())

async def on_callback_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data.startswith("OPENPAPER|"):
        sym = q.data.split("|", 1)[1]
        try:
            res = analyze(DEFAULT_EXCHANGE, sym, DEFAULT_TIMEFRAME, DEFAULT_LIMIT)
            if not res.get("side"):
                await q.edit_message_text("🟡 ما عادش setup واضح الآن.", reply_markup=main_menu())
                return
            ok, msg = paper_open(uid, res["symbol"], res["side"], res["entry"], res["sl"], res["tp"], size_usd=50.0)
            await q.edit_message_text(msg, reply_markup=main_menu())
        except Exception as e:
            await q.edit_message_text(f"❌ {e}", reply_markup=main_menu())
        return

def run():
    token = env_token()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN (or TELEGRAM_TOKEN) in ENV")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback_extra, pattern=r"^OPENPAPER\|"))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # ✅ هذا الصحيح في PTB 21: بدون await وبدون asyncio.run
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    run()
