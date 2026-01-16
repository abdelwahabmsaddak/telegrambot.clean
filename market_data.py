import os
import requests
import yfinance as yf
from utils import normalize_symbol

BINANCE = "https://api.binance.com"

def crypto_price_usd(symbol: str) -> float | None:
    sym = normalize_symbol(symbol)
    pair = f"{sym}USDT"
    try:
        r = requests.get(f"{BINANCE}/api/v3/ticker/price", params={"symbol": pair}, timeout=12)
        if r.status_code != 200:
            return None
        return float(r.json()["price"])
    except:
        return None

def stock_price(symbol: str) -> float | None:
    sym = normalize_symbol(symbol)
    try:
        t = yf.Ticker(sym)
        info = t.fast_info
        p = info.get("last_price")
        if p is not None:
            return float(p)
        h = t.history(period="1d")
        if len(h) == 0:
            return None
        return float(h["Close"].iloc[-1])
    except:
        return None

def gold_price() -> float | None:
    # نستخدم الذهب futures كقيمة تقريبية
    try:
        t = yf.Ticker("GC=F")
        h = t.history(period="1d")
        if len(h) == 0:
            return None
        return float(h["Close"].iloc[-1])
    except:
        return None

def get_asset_price(symbol: str) -> tuple[str, float | None]:
    sym = normalize_symbol(symbol)
    if sym == "XAU":
        return ("GOLD", gold_price())
    # كريبتو أولاً
    p = crypto_price_usd(sym)
    if p is not None:
        return ("CRYPTO", p)
    # أسهم
    return ("STOCK", stock_price(sym))

def top_crypto_movers(limit: int = 8):
    # “صيد فرص”: أعلى تغيّر + حجم
    try:
        r = requests.get(f"{BINANCE}/api/v3/ticker/24hr", timeout=15)
        r.raise_for_status()
        data = r.json()
        # فلترة USDT فقط
        usdt = [x for x in data if x.get("symbol","").endswith("USDT")]
        # رتب على نسبة التغيّر
        usdt.sort(key=lambda x: float(x.get("priceChangePercent", 0.0)), reverse=True)
        out = []
        for item in usdt[:limit]:
            out.append({
                "symbol": item["symbol"].replace("USDT", ""),
                "chg": float(item["priceChangePercent"]),
                "vol": float(item.get("quoteVolume", 0.0)),
                "last": float(item.get("lastPrice", 0.0)),
            })
        return out
    except:
        return []

def whale_alert_recent(min_usd: int = 200000):
    # اختياري: يلزم WHALE_ALERT_KEY
    key = os.environ.get("WHALE_ALERT_KEY", "").strip()
    if not key:
        return None  # not enabled
    try:
        url = "https://api.whale-alert.io/v1/transactions"
        params = {"api_key": key, "min_value": min_usd, "currency": "usd"}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        txs = data.get("transactions", [])[:6]
        return txs
    except:
        return []
