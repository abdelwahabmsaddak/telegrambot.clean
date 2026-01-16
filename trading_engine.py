from dataclasses import dataclass, asdict
from typing import Dict, Any
from data_providers import get_asset_price
from analysis_engine import build_signal

_USERS: Dict[int, Dict[str, Any]] = {}
_PAPER: Dict[int, Dict[str, Any]] = {}  # uid -> {symbol: {...}}

DEFAULT_USER = {"lang": "auto", "platform": "binance", "risk": 1.0}

def get_user(uid: int) -> Dict[str, Any]:
    if uid not in _USERS:
        _USERS[uid] = dict(DEFAULT_USER)
    return _USERS[uid]

def set_user(uid: int, **kwargs):
    u = get_user(uid)
    u.update(kwargs)

def reset_user(uid: int):
    _USERS[uid] = dict(DEFAULT_USER)
    _PAPER.pop(uid, None)

def _price(sym: str):
    sym = normalize_symbol_guess(sym)
    if sym == "XAU":
        return get_gold_quote()
    if sym in CRYPTO_MAP:
        return get_crypto_quote(sym)
    return get_stock_quote(sym)

def build_trade_idea(symbol: str, risk_pct: float, platform: str) -> str:
    sym = normalize_symbol_guess(symbol)
    p = _price(sym)
    snap = quick_market_snapshot(sym)

    if not p:
        return f"❌ ما نجمتش نجيب سعر {sym} حالياً."

    # فكرة بسيطة: نطاقات تقريبية + SL/TP
    # (مش توصية مضمونة — مجرد إطار عمل)
    # SL = risk-based distance
    risk_pct = max(0.1, min(risk_pct, 10.0))
    sl_dist = p * (risk_pct / 100.0)
    sl = p - sl_dist
    tp1 = p + (sl_dist * 1.2)
    tp2 = p + (sl_dist * 2.0)

    return (
        f"📌 Trade Idea (بدون تنفيذ) — {sym}\n"
        f"🧾 Platform: {platform}\n"
        f"{snap}\n\n"
        f"✅ سيناريو محافظ:\n"
        f"- Entry: قرب {p:.6f}\n"
        f"- Stop Loss (تقريبي): {sl:.6f}  (≈ {risk_pct}% من السعر)\n"
        f"- Take Profit 1: {tp1:.6f}\n"
        f"- Take Profit 2: {tp2:.6f}\n\n"
        f"🛡️ إدارة مخاطر:\n"
        f"- لا تخاطر بأكثر من {risk_pct}% على الصفقة.\n"
        f"- قسّم الدخول (DCA) إذا تحب.\n\n"
        f"⚠️ تنبيه: هذا إطار عمل تعليمي وليس ضمان ربح."
    )

def paper_trade_open(uid: int, symbol: str, side: str, usd: float) -> str:
    sym = normalize_symbol_guess(symbol)
    side = side.lower()
    if side not in ("buy", "sell"):
        return "❌ side لازم buy أو sell"
    if usd <= 0:
        return "❌ المبلغ لازم > 0"

    p = _price(sym)
    if not p:
        return f"❌ ما نجمتش نجيب سعر {sym}"

    qty = usd / p
    _PAPER.setdefault(uid, {})
    _PAPER[uid][sym] = {
        "symbol": sym,
        "side": side,
        "usd": usd,
        "entry": p,
        "qty": qty,
        "opened_at": str(__import__("datetime").datetime.utcnow()),
    }
    return f"✅ Paper Opened: {sym} {side} | entry={p:.6f} | qty≈{qty:.6f}"

def paper_trade_close(uid: int, symbol: str) -> str:
    sym = normalize_symbol_guess(symbol)
    if uid not in _PAPER or sym not in _PAPER[uid]:
        return "❌ ما فماش صفقة مفتوحة على هذا الرمز."
    pos = _PAPER[uid][sym]
    p = _price(sym)
    if not p:
        return f"❌ ما نجمتش نجيب سعر {sym}"

    entry = pos["entry"]
    side = pos["side"]
    qty = pos["qty"]

    pnl = (p - entry) * qty if side == "buy" else (entry - p) * qty
    pnl_pct = (pnl / pos["usd"]) * 100.0

    del _PAPER[uid][sym]
    return f"✅ Paper Closed: {sym} | exit={p:.6f} | PnL={pnl:.4f}$ ({pnl_pct:.2f}%)"

def paper_trade_status(uid: int) -> str:
    if uid not in _PAPER or not _PAPER[uid]:
        return "📭 ما عندك حتى Paper Trades مفتوحة."
    lines = ["📌 Paper Trades المفتوحة:"]
    for sym, pos in _PAPER[uid].items():
        p = _price(sym) or pos["entry"]
        entry = pos["entry"]
        qty = pos["qty"]
        side = pos["side"]
        pnl = (p - entry) * qty if side == "buy" else (entry - p) * qty
        pnl_pct = (pnl / pos["usd"]) * 100.0
        lines.append(f"- {sym} {side} entry={entry:.6f} now={p:.6f} PnL={pnl:.2f}$ ({pnl_pct:.2f}%)")
    return "\n".join(lines)
# ===== Paper Trading API =====

def paper_open(user_id, symbol, side, amount):
    return {
        "status": "opened",
        "user": user_id,
        "symbol": symbol,
        "side": side,
        "amount": amount
    }

def paper_close(user_id, symbol):
    return {
        "status": "closed",
        "user": user_id,
        "symbol": symbol
    }
