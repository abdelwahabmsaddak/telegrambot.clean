# strategy.py
import math

def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n

def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        diff = closes[i] - closes[i-1]
        if diff >= 0:
            gains += diff
        else:
            losses += -diff
    if losses == 0:
        return 100.0
    rs = gains / losses
    return 100.0 - (100.0 / (1.0 + rs))

def trend_score(closes):
    # simple: SMA20 vs SMA50
    s20 = sma(closes, 20)
    s50 = sma(closes, 50)
    if s20 is None or s50 is None:
        return 0
    return 1 if s20 > s50 else -1

def pick_opportunity(symbol, closes):
    # simple opportunity: trend + RSI
    t = trend_score(closes)
    r = rsi(closes, 14)
    if r is None:
        return None
    if t == 1 and r < 45:
        return ("BUY", f"Uptrend + RSI={r:.1f} (pullback)")
    if t == -1 and r > 55:
        return ("SELL", f"Downtrend + RSI={r:.1f} (pullback)")
    return None
