from analysis import analyze
from signals import signal
from ai_chat import chat
from whale import scan_whales

def route_message(text):
    t = text.lower()

    if "تحليل" in t or "btc" in t or "eth" in t:
        return analyze(t)

    if "إشارة" in t or "صفقة" in t:
        return signal(t)

    if "حيتان" in t or "volume" in t:
        return scan_whales()

    return chat(text)
