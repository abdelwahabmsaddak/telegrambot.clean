# market_data.py
import time
import requests
from utils import sanitize_text

BINANCE_BASE = "https://api.binance.com"

def binance_top_symbols(limit: int = 80):
    # Top USDT pairs by quoteVolume
    r = requests.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", timeout=20)
    r.raise_for_status()
    data = r.json()
    usdt = [x for x in data if x.get("symbol","").endswith("USDT")]
    usdt.sort(key=lambda x: float(x.get("quoteVolume", 0.0)), reverse=True)
    return [x["symbol"] for x in usdt[:limit]]

def binance_price(symbol: str):
    r = requests.get(f"{BINANCE_BASE}/api/v3/ticker/price", params={"symbol": symbol}, timeout=20)
    r.raise_for_status()
    p = float(r.json()["price"])
    return p, int(time.time())

def binance_klines(symbol: str, interval="1h", limit=120):
    r = requests.get(
        f"{BINANCE_BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=20,
    )
    r.raise_for_status()
    kl = r.json()
    # [openTime, open, high, low, close, volume, ...]
    o = [float(x[1]) for x in kl]
    h = [float(x[2]) for x in kl]
    l = [float(x[3]) for x in kl]
    c = [float(x[4]) for x in kl]
    v = [float(x[5]) for x in kl]
    return o, h, l, c, v

def stooq_daily_csv(ticker: str):
    # Daily CSV: Date,Open,High,Low,Close,Volume
    url = f"https://stooq.com/q/d/l/?s={ticker}&i=d"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    lines = r.text.strip().splitlines()
    if len(lines) < 3:
        return None
    rows = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        rows.append(parts)
    return rows

def stooq_last_close(ticker: str):
    rows = stooq_daily_csv(ticker)
    if not rows:
        return None
    last = rows[-1]
    close = float(last[4])
    return close, int(time.time())

def stooq_series_close(ticker: str, last_n=180):
    rows = stooq_daily_csv(ticker)
    if not rows:
        return None
    rows = rows[-last_n:]
    closes = [float(r[4]) for r in rows]
    return closes

def normalize_asset(asset: str):
    a = sanitize_text(asset).upper()
    if a in ("GOLD", "XAU", "XAUUSD"):
        return ("gold", "xauusd")  # stooq gold
    # stock: TSLA / AAPL => stooq needs .US often
    if a.isalpha() and 1 < len(a) <= 6:
        return ("stock", f"{a}.US")
    # crypto: user might type BTC -> use BTCUSDT
    if a.isalpha() and len(a) <= 6:
        return ("crypto", f"{a}USDT")
    # already a binance symbol like BTCUSDT
    if a.endswith("USDT"):
        return ("crypto", a)
    return ("unknown", a)
