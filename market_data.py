import os
import math
import requests
import yfinance as yf

COINGECKO = "https://api.coingecko.com/api/v3"

CRYPTO_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "FLOKI": "floki",
    "PEPE": "pepe",
    "WIF": "dogwifcoin",
}

def normalize_symbol_guess(sym: str) -> str:
    sym = sym.upper().strip()
    # ذهب
    if sym in ("XAU", "GOLD"):
        return "XAU"
    # بيتكوين وهكذا
    if sym in CRYPTO_MAP:
        return sym
    # سهم
    return sym  # TSLA/AAPL...

def get_crypto_quote(symbol: str):
    sid = CRYPTO_MAP.get(symbol.upper())
    if not sid:
        return None
    url = f"{COINGECKO}/simple/price"
    r = requests.get(url, params={"ids": sid, "vs_currencies": "usd"}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return float(data[sid]["usd"])

def get_stock_quote(ticker: str):
    t = yf.Ticker(ticker)
    info = t.fast_info
    price = info.get("last_price", None)
    if price is None:
        hist = t.history(period="1d")
        if len(hist) == 0:
            return None
        price = float(hist["Close"].iloc[-1])
    return float(price)

def get_gold_quote():
    # حل سريع: نعتبر XAUUSD موجود في Yahoo Finance كـ "GC=F" (ذهب futures)
    # تنجم تبدله لـ XAUUSD=X حسب availability
    try:
        t = yf.Ticker("GC=F")
        hist = t.history(period="1d")
        if len(hist) == 0:
            return None
        return float(hist["Close"].iloc[-1])
    except:
        return None

def quick_market_snapshot(symbol: str) -> str:
    symbol = normalize_symbol_guess(symbol)
    try:
        if symbol == "XAU":
            p = get_gold_quote()
            return f"- Gold (approx): {p} USD" if p else "- Gold: N/A"
        if symbol in CRYPTO_MAP:
            p = get_crypto_quote(symbol)
            return f"- {symbol} price: {p} USD" if p else f"- {symbol}: N/A"
        # Stock
        p = get_stock_quote(symbol)
        return f"- {symbol} price: {p} USD" if p else f"- {symbol}: N/A"
    except Exception as e:
        return f"- snapshot error: {e}"
