# bot.py
import os
import time
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from utils import sanitize_text, detect_lang_auto
from ai_engine import AIEngine
from market_data import (
    normalize_asset, binance_top_symbols, binance_price, binance_klines,
    stooq_last_close, stooq_series_close
)
from strategy import pick_opportunity
from charts import plot_closes_image
from trader import Trader

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("smartbot")

TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

@dataclass
class UserCfg:
    lang: str = "auto"        # auto/ar/en
    auto_on: bool = False     # client chooses
    auto_scope: str = "all"   # all/crypto/gold/stocks
    auto_mode: str = "paper"  # paper/live (live optional later)
    scan_n: int = 40          # how many crypto pairs to scan (top by volume)

USERS: Dict[int, UserCfg] = {}
AI = AIEngine()
TRADER = Trader()

def get_user(uid: int) -> UserCfg:
    if uid not in USERS:
        USERS[uid] = UserCfg()
    return USERS[uid]

def ui(lang: str):
    if lang == "ar":
        keys = [
            [KeyboardButton("📊 تحليل"), KeyboardButton("🖼️ صورة")],
            [KeyboardButton("🔎 فرص اليوم"), KeyboardButton("🤖 Auto تشغيل/إيقاف")],
            [KeyboardButton("⚙️ إعدادات"), KeyboardButton("🧠 دردشة")],
        ]
    else:
        keys = [
            [KeyboardButton("📊 Analysis"), KeyboardButton("🖼️ Chart")],
            [KeyboardButton("🔎 Scan"), KeyboardButton("🤖 Auto ON/OFF")],
            [KeyboardButton("⚙️ Settings"), KeyboardButton("🧠 Chat")],
        ]
    return ReplyKeyboardMarkup(keys, resize_keyboard=True)

def resolve_lang(u: UserCfg, text: str) -> str:
    if u.lang in ("ar", "en"):
        return u.lang
    return detect_lang_auto(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    lang = resolve_lang(u, "مرحبا")
    msg_ar = (
        "✅ البوت جاهز (أسعار Live + تحليل + صور + Auto اختياري)\n\n"
        "أوامر:\n"
        "/lang ar | en | auto\n"
        "/auto on | off\n"
        "/auto scope all|crypto|gold|stocks\n"
        "/auto mode paper|live (live اختياري لاحقًا)\n"
        "/scan (فرص)\n"
        "/analysis BTC أو TSLA أو XAUUSD\n"
        "/chart BTC أو TSLA أو XAUUSD\n"
        "/paper status|close\n\n"
        "اكتب سؤالك وسيجيب الذكاء الاصطناعي."
    )
    msg_en = (
        "✅ Bot ready (Live prices + analysis + charts + optional Auto)\n\n"
        "Commands:\n"
        "/lang ar | en | auto\n"
        "/auto on | off\n"
        "/auto scope all|crypto|gold|stocks\n"
        "/auto mode paper|live (live optional later)\n"
        "/scan\n"
        "/analysis BTC or TSLA or XAUUSD\n"
        "/chart BTC or TSLA or XAUUSD\n"
        "/paper status|close\n\n"
        "Type any question and the AI will reply."
    )
    await update.message.reply_text(msg_ar if lang == "ar" else msg_en, reply_markup=ui(lang))

async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    arg = (context.args[0].lower().strip() if context.args else "auto")
    if arg not in ("auto", "ar", "en"):
        arg = "auto"
    u.lang = arg
    lang = resolve_lang(u, update.message.text or "")
    await update.message.reply_text(
        ("✅ تم ضبط اللغة" if lang == "ar" else "✅ Language set"),
        reply_markup=ui(lang)
    )

async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    lang = resolve_lang(u, update.message.text or "")
    if not context.args:
        await update.message.reply_text(
            (f"Auto: {'ON' if u.auto_on else 'OFF'} | scope={u.auto_scope} | mode={u.auto_mode}"
             if lang == "en" else
             f"Auto: {'مفعّل' if u.auto_on else 'موقوف'} | النطاق={u.auto_scope} | الوضع={u.auto_mode}"),
            reply_markup=ui(lang)
        )
        return

    sub = context.args[0].lower()
    if sub in ("on", "off"):
        u.auto_on = (sub == "on")
    elif sub == "scope" and len(context.args) >= 2:
        sc = context.args[1].lower()
        if sc in ("all", "crypto", "gold", "stocks"):
            u.auto_scope = sc
    elif sub == "mode" and len(context.args) >= 2:
        md = context.args[1].lower()
        # live موجود لكن نخليه اختياري لاحقًا، حاليا paper هو الآمن
        if md in ("paper", "live"):
            u.auto_mode = md

    await update.message.reply_text(
        ("✅ تم تحديث Auto" if lang == "ar" else "✅ Auto updated"),
        reply_markup=ui(lang)
    )

async def paper_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = resolve_lang(u, update.message.text or "")
    if not context.args:
        tr = TRADER.status(uid)
        if not tr:
            await update.message.reply_text("📭 لا توجد صفقات Paper" if lang == "ar" else "📭 No paper trades.")
        else:
            await update.message.reply_text(f"🧾 {tr.asset} {tr.side} | {tr.status}\nReason: {tr.reason}")
        return
    sub = context.args[0].lower()
    if sub == "status":
        tr = TRADER.status(uid)
        if not tr:
            await update.message.reply_text("📭 لا توجد صفقات Paper" if lang == "ar" else "📭 No paper trades.")
        else:
            await update.message.reply_text(f"🧾 {tr.asset} {tr.side} | {tr.status}\nReason: {tr.reason}")
    elif sub == "close":
        tr = TRADER.close_paper(uid)
        await update.message.reply_text("✅ تم إغلاق Paper" if lang == "ar" else "✅ Paper closed.")

def live_snapshot(asset: str) -> str:
    kind, sym = normalize_asset(asset)
    if kind == "crypto":
        price, ts = binance_price(sym)
        return f"{sym} price={price:.6f} (ts={ts})"
    if kind == "gold":
        close, ts = stooq_last_close(sym)
        return f"XAUUSD close={close:.2f} (ts={ts})"
    if kind == "stock":
        close, ts = stooq_last_close(sym)
        return f"{sym} close={close:.2f} (ts={ts})"
    return f"{asset} no data"

async def analysis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    lang = resolve_lang(u, update.message.text or "")
    asset = context.args[0] if context.args else "BTC"
    asset = sanitize_text(asset)

    snap = live_snapshot(asset)
    prompt = (f"حلّل {asset} الآن بشكل احترافي. ابدأ بسعر حي من السياق، ثم اتجاه، دعم/مقاومة، "
              f"سيناريو صعود/هبوط، وإدارة مخاطر. وأرفق نصائح واضحة."
              if lang == "ar" else
              f"Analyze {asset} professionally using the live context price. Provide trend, S/R, bull/bear scenarios and risk management.")

    ans = AI.answer(lang=lang, user_text=prompt, context_hint=snap)
    await update.message.reply_text(ans, reply_markup=ui(lang))

async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    lang = resolve_lang(u, update.message.text or "")
    asset = context.args[0] if context.args else "BTC"
    asset = sanitize_text(asset)

    kind, sym = normalize_asset(asset)
    path = f"/tmp/{sym}_chart.png"

    closes = None
    title = sym

    if kind == "crypto":
        _, _, _, c, _ = binance_klines(sym, interval="1h", limit=120)
        closes = c
        title = f"{sym} (1h) - Live"
    elif kind in ("gold", "stock"):
        s = stooq_series_close(sym, last_n=180)
        closes = s
        title = f"{sym} (Daily) - Stooq"

    if not closes:
        await update.message.reply_text("❌ لم أستطع توليد صورة الآن" if lang == "ar" else "❌ Could not generate chart.")
        return

    plot_closes_image(title, closes, path)
    with open(path, "rb") as f:
        cap = "🖼️ صورة تحليل" if lang == "ar" else "🖼️ Analysis chart"
        await update.message.reply_photo(photo=InputFile(f), caption=cap, reply_markup=ui(lang))

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    lang = resolve_lang(u, update.message.text or "")
    # scan top N crypto by volume + gold + one stock example (full stocks scanning is huge)
    top = binance_top_symbols(limit=u.scan_n)

    picks = []
    for sym in top:
        try:
            _, _, _, c, _ = binance_klines(sym, interval="1h", limit=120)
            opp = pick_opportunity(sym, c)
            if opp:
                side, reason = opp
                picks.append((sym, side, reason))
            if len(picks) >= 5:
                break
        except Exception:
            continue

    # gold
    gold_series = stooq_series_close("xauusd", last_n=180)
    if gold_series:
        opp = pick_opportunity("XAUUSD", gold_series)
        if opp and len(picks) < 6:
            picks.append(("XAUUSD", opp[0], opp[1]))

    if not picks:
        await update.message.reply_text("لا توجد فرص قوية الآن." if lang == "ar" else "No strong opportunities right now.")
        return

    lines = []
    for sym, side, reason in picks[:6]:
        lines.append(f"- {sym}: {side} | {reason}")

    msg = ("🔎 أفضل فرص (فلترة بسيطة):\n" if lang == "ar" else "🔎 Top opportunities (simple filter):\n") + "\n".join(lines)
    await update.message.reply_text(msg, reply_markup=ui(lang))

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    text = sanitize_text(update.message.text or "")
    if not text:
        return
    lang = resolve_lang(u, text)

    # buttons
    if text in ("📊 تحليل", "📊 Analysis"):
        await update.message.reply_text("اكتب الرمز (BTC / TSLA / XAUUSD)" if lang == "ar" else "Send a symbol (BTC / TSLA / XAUUSD)")
        return
    if text in ("🖼️ صورة", "🖼️ Chart"):
        await update.message.reply_text("اكتب الرمز للصورة" if lang == "ar" else "Send a symbol for the chart")
        return
    if text in ("🔎 فرص اليوم", "🔎 Scan"):
        await scan_cmd(update, context)
        return
    if text in ("🤖 Auto تشغيل/إيقاف", "🤖 Auto ON/OFF"):
        u.auto_on = not u.auto_on
        await update.message.reply_text(
            ("✅ Auto مفعّل" if u.auto_on and lang == "ar" else
             "⛔ Auto موقوف" if (not u.auto_on and lang == "ar") else
             "✅ Auto ON" if u.auto_on else "⛔ Auto OFF"),
            reply_markup=ui(lang)
        )
        return
    if text in ("⚙️ إعدادات", "⚙️ Settings"):
        await update.message.reply_text(
            ("/auto on|off\n/auto scope all|crypto|gold|stocks\n/auto mode paper|live\n/scan\n/analysis BTC\n/chart BTC\n"
             if lang == "ar" else
             "/auto on|off\n/auto scope all|crypto|gold|stocks\n/auto mode paper|live\n/scan\n/analysis BTC\n/chart BTC\n"),
            reply_markup=ui(lang)
        )
        return
    if text in ("🧠 دردشة", "🧠 Chat"):
        await update.message.reply_text("اكتب سؤالك." if lang == "ar" else "Ask your question.")
        return

    # If user wrote a symbol only -> do analysis
    if text.isalpha() and len(text) <= 7:
        context.args = [text]
        await analysis_cmd(update, context)
        return

    # normal AI chat
    hint = "User enabled Auto (paper/live) is optional. Provide educational guidance."
    ans = AI.answer(lang=lang, user_text=text, context_hint=hint)
    await update.message.reply_text(ans, reply_markup=ui(lang))

async def auto_loop(context: ContextTypes.DEFAULT_TYPE):
    # Runs periodically; picks opportunities only if user enabled auto_on
    for uid, u in list(USERS.items()):
        if not u.auto_on:
            continue

        # scope decide what to scan
        picks = []
        if u.auto_scope in ("all", "crypto"):
            top = binance_top_symbols(limit=u.scan_n)
            for sym in top:
                try:
                    _, _, _, c, _ = binance_klines(sym, interval="1h", limit=120)
                    opp = pick_opportunity(sym, c)
                    if opp:
                        side, reason = opp
                        picks.append((sym, side, reason))
                    if len(picks) >= 1:
                        break
                except Exception:
                    continue

        if u.auto_scope in ("all", "gold") and not picks:
            s = stooq_series_close("xauusd", last_n=180)
            if s:
                opp = pick_opportunity("XAUUSD", s)
                if opp:
                    picks.append(("XAUUSD", opp[0], opp[1]))

        # stocks scanning “all stocks” huge; we keep it enabled but not mass-scan by default.
        # later: user adds watchlist or we integrate screener.
        if u.auto_scope in ("all", "stocks") and not picks:
            # placeholder: no scan until watchlist is added later
            pass

        if not picks:
            continue

        sym, side, reason = picks[0]
        # Paper trade open (safe)
        tr = TRADER.open_paper(uid, sym, side, reason)
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"🤖 AUTO (PAPER) OPEN\n{tr.asset} {tr.side}\nReason: {tr.reason}",
            )
        except Exception:
            pass

def main():
    from telegram.ext import ApplicationBuilder

app = (
    ApplicationBuilder()
    .token(TOKEN)
    .build()
)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CommandHandler("auto", auto_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("analysis", analysis_cmd))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(CommandHandler("paper", paper_cmd))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Auto engine job: runs every 2 minutes
    app.job_queue.run_repeating(auto_loop, interval=120, first=20)

    log.info("🤖 BOT RUNNING...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
