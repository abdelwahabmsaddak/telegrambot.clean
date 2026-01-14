import os
import time
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from market_data import normalize_symbol_guess, CRYPTO_MAP

def _fetch_series(sym: str):
    # crypto: نستعمل Yahoo tickers مثل BTC-USD
    if sym in CRYPTO_MAP:
        ticker = f"{sym}-USD"
    elif sym == "XAU":
        ticker = "GC=F"
    else:
        ticker = sym

    t = yf.Ticker(ticker)
    hist = t.history(period="30d", interval="1d")
    if len(hist) == 0:
        return None, ticker
    return hist, ticker

def build_price_chart_png(symbol: str):
    sym = normalize_symbol_guess(symbol)
    hist, ticker = _fetch_series(sym)
    if hist is None:
        return None, None

    ts = int(time.time())
    out = f"/tmp/chart_{sym}_{ts}.png"

    plt.figure()
    plt.plot(hist.index, hist["Close"])
    plt.title(f"{sym} ({ticker}) - 30D Close")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()

    last = float(hist["Close"].iloc[-1])
    caption = f"📈 {sym} آخر سعر تقريبي: {last:.4f}"
    return out, caption
