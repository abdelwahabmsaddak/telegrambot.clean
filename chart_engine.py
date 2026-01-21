import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime

def generate_chart(symbol: str):
    ticker_map = {
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "XAUUSD": "GC=F",
        "TSLA": "TSLA"
    }

    yf_symbol = ticker_map.get(symbol)
    if not yf_symbol:
        return None

    data = yf.download(yf_symbol, period="7d", interval="1h")

    if data.empty:
        return None

    plt.figure(figsize=(10, 4))
    plt.plot(data.index, data["Close"], label="Price")
    plt.title(f"{symbol} Price Chart")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.grid(True)
    plt.legend()

    file_name = f"/tmp/{symbol}_chart.png"
    plt.savefig(file_name)
    plt.close()

    return file_name
