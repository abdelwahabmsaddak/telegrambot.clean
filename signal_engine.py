import random

def generate_signal(symbol, data):
    price = data["price"]
    ema50 = data["ema50"]
    ema200 = data["ema200"]
    rsi = data["rsi"]
    volume = data["volume"]
    support = data["support"]
    resistance = data["resistance"]

    signal = None

    # LONG شروط
    if ema50 > ema200 and 50 < rsi < 70 and price > support and volume == "positive":
        signal = {
            "type": "LONG",
            "confidence": random.randint(65, 78),
            "entry": (price * 0.995, price * 1.002),
            "tp1": price * 1.015,
            "tp2": price * 1.03,
            "sl": price * 0.985,
            "bias": "Bullish",
            "strategy": "Trend Continuation + Pullback"
        }

    # SHORT شروط
    elif ema50 < ema200 and 30 < rsi < 50 and price < resistance and volume == "negative":
        signal = {
            "type": "SHORT",
            "confidence": random.randint(65, 78),
            "entry": (price * 0.998, price * 1.005),
            "tp1": price * 0.985,
            "tp2": price * 0.97,
            "sl": price * 1.015,
            "bias": "Bearish",
            "strategy": "Trend Continuation + Rejection"
        }

    return signal
