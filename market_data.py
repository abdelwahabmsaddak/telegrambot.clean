from exchange_engine import get_exchange

def get_price(symbol, exchange_name="bybit"):
    ex = get_exchange(exchange_name)
    ticker = ex.fetch_ticker(symbol)
    return ticker["last"]
