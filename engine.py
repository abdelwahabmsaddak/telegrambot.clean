from typing import Dict, Optional, List, Tuple
import numpy as np
import pandas as pd
from services import fetch_ohlcv, list_usdt_symbols, fetch_ticker
from storage import paper_get, paper_set, log_event

def _df_from_ohlcv(ohlcv) -> pd.DataFrame:
    df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms")
    return df

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/period, adjust=False).mean()
    ma_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = ma_up / (ma_down.replace(0, np.nan))
    return 100 - (100 / (1 + rs))

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def macd(series: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    fast = ema(series, 12)
    slow = ema(series, 26)
    macd_line = fast - slow
    signal = ema(macd_line, 9)
    hist = macd_line - signal
    return macd_line, signal, hist

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]; low = df["low"]; close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high-low).abs(), (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def analyze(exchange: str, symbol: str, timeframe: str, limit: int) -> Dict:
    ohlcv, sym = fetch_ohlcv(exchange, symbol, timeframe, limit)
    df = _df_from_ohlcv(ohlcv)

    df["rsi"] = rsi(df["close"])
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    m_line, s_line, hist = macd(df["close"])
    df["macd"] = m_line
    df["macd_sig"] = s_line
    df["macd_hist"] = hist
    df["atr"] = atr(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    trend_up = last["ema20"] > last["ema50"]
    macd_up = last["macd_hist"] > 0 and last["macd_hist"] > prev["macd_hist"]
    macd_down = last["macd_hist"] < 0 and last["macd_hist"] < prev["macd_hist"]

    # Signal logic (simple but real)
    side = None
    if trend_up and macd_up and last["rsi"] < 70:
        side = "LONG"
    elif (not trend_up) and macd_down and last["rsi"] > 30:
        side = "SHORT"

    price = float(last["close"])
    a = float(last["atr"]) if not np.isnan(last["atr"]) else price * 0.005

    # Risk model
    risk_atr = 1.5 * a
    rr = 2.0

    if side == "LONG":
        entry = price
        sl = entry - risk_atr
        tp = entry + risk_atr * rr
    elif side == "SHORT":
        entry = price
        sl = entry + risk_atr
        tp = entry - risk_atr * rr
    else:
        entry = sl = tp = None

    return {
        "symbol": sym,
        "exchange": exchange,
        "timeframe": timeframe,
        "price": price,
        "rsi": float(last["rsi"]) if not np.isnan(last["rsi"]) else None,
        "ema20": float(last["ema20"]),
        "ema50": float(last["ema50"]),
        "macd_hist": float(last["macd_hist"]),
        "atr": float(last["atr"]) if not np.isnan(last["atr"]) else None,
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "rr": rr if side else None,
    }

def format_signal(res: Dict) -> str:
    s = []
    s.append(f"📌 {res['symbol']}  |  {res['exchange']}  |  {res['timeframe']}")
    s.append(f"💰 Price: {res['price']:.6g}")
    s.append(f"📈 RSI: {res['rsi']:.2f} | EMA20/50: {res['ema20']:.6g} / {res['ema50']:.6g}")
    s.append(f"⚙️ MACD hist: {res['macd_hist']:.6g} | ATR: {res['atr']:.6g}" if res["atr"] else f"⚙️ MACD hist: {res['macd_hist']:.6g}")

    if not res["side"]:
        s.append("🟡 No clean setup right now.")
        return "\n".join(s)

    s.append(f"🎯 Signal: {res['side']}")
    s.append(f"Entry: {res['entry']:.6g}")
    s.append(f"SL: {res['sl']:.6g}")
    s.append(f"TP: {res['tp']:.6g}")
    s.append(f"R/R: {res['rr']:.2f}")
    return "\n".join(s)

def scan(exchange: str, timeframe: str, limit: int, top: int = 10) -> List[Dict]:
    symbols = list_usdt_symbols(exchange)
    # reduce workload
    symbols = symbols[: min(len(symbols), 120)]
    out = []
    for sym in symbols:
        try:
            res = analyze(exchange, sym, timeframe, limit)
            if res["side"]:
                score = abs(res["macd_hist"]) + (0 if res["rsi"] is None else abs(50 - res["rsi"]) / 50)
                out.append({**res, "score": float(score)})
        except Exception:
            continue
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top]

# ---------------- Paper trading ----------------
def paper_open(uid: int, symbol: str, side: str, entry: float, sl: float, tp: float, size_usd: float = 50.0):
    st = paper_get(uid)
    if st["balance"] < size_usd:
        return False, "رصيد Paper غير كافي."
    st["balance"] -= size_usd
    st["positions"].append({"symbol": symbol, "side": side, "entry": entry, "sl": sl, "tp": tp, "usd": size_usd})
    paper_set(uid, st)
    log_event({"type": "paper_open", "uid": uid, "symbol": symbol, "side": side, "usd": size_usd})
    return True, f"✅ Paper opened {side} {symbol} (${size_usd})"

def paper_status(uid: int) -> str:
    st = paper_get(uid)
    lines = [f"💼 Paper Balance: ${st['balance']:.2f}", f"📦 Positions: {len(st['positions'])}"]
    for p in st["positions"][-10:]:
        lines.append(f"- {p['symbol']} {p['side']} entry {p['entry']:.6g} SL {p['sl']:.6g} TP {p['tp']:.6g} (${p['usd']})")
    return "\n".join(lines)
