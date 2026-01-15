from analysis import analyze_asset
from signals import generate_signal
from scanner import find_opportunity
from chat_ai import ai_reply

def route_message(text: str) -> str:
    t = text.lower()

    if any(x in t for x in ["btc", "eth", "gold", "xau", "tsla"]):
        return analyze_asset(t)

    if any(x in t for x in ["صفقة", "signal", "شراء", "بيع"]):
        return generate_signal(t)

    if any(x in t for x in ["عملة رابحة", "فرصة", "صيد"]):
        return find_opportunity()

    return ai_reply(text)
