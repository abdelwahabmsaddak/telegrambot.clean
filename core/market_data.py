import requests

def get_crypto_price(symbol: str) -> float | None:
    # Binance public (مثال BTC -> BTCUSDT)
    pair = symbol.upper().replace("/", "") + "USDT"
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return None
    return float(r.json()["price"])

def get_stock_price(symbol: str) -> float | None:
    # مصدر بسيط مجاني: stooq
    s = symbol.lower()
    url = f"https://stooq.com/q/l/?s={s}&f=sd2t2ohlcv&h&e=csv"
    r = requests.get(url, timeout=10)
    if r.status_code != 200 or "Close" not in r.text:
        return None
    lines = r.text.strip().splitlines()
    if len(lines) < 2:
        return None
    close = lines[1].split(",")[6]
    return None if close == "N/A" else float(close)

def get_gold_price() -> float | None:
    # حل بسيط: نرجّعو None الآن ونعوّضوه بمزوّد ثابت في V1.1
    return None
