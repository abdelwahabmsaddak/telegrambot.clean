import ccxt

SUPPORTED_EXCHANGES = {
    "binance": ccxt.binance,
    "bybit": ccxt.bybit,
    "okx": ccxt.okx,
    "kucoin": ccxt.kucoin,
}

def get_exchange(name, api_key=None, secret=None):
    if name not in SUPPORTED_EXCHANGES:
        raise ValueError("❌ منصة غير مدعومة")

    params = {"enableRateLimit": True}

    if api_key and secret:
        params["apiKey"] = api_key
        params["secret"] = secret

    return SUPPORTED_EXCHANGES[name](params)
