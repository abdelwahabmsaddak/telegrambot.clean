# -*- coding: utf-8 -*-

from utils import safe_text

def ai_chat(prompt: str) -> str:
    """
    AI Core (Clean & Safe)
    """

    text = prompt.strip().lower()

    # ---- عربي ----
    if "بيتكوين" in text or "btc" in text:
        return safe_text(
            "📊 تحليل BTC:\n"
            "الاتجاه العام: عرضي\n"
            "الدعم: 42000\n"
            "المقاومة: 44500\n"
            "إدارة المخاطر ضرورية."
        )

    if "ذهب" in text or "gold" in text or "xau" in text:
        return safe_text(
            "🟡 تحليل الذهب:\n"
            "الاتجاه: صاعد متوسط\n"
            "الدعم: 2010\n"
            "المقاومة: 2055"
        )

    # ---- English ----
    if "analysis" in text:
        return safe_text(
            "📈 Market Analysis:\n"
            "Trend: Neutral\n"
            "Risk management is recommended."
        )

    # ---- Default (ChatGPT-like) ----
    return safe_text(
        "🤖 AI Response:\n"
        "سؤالك وصل ✔\n"
        "يمكنك السؤال عن:\n"
        "- Crypto\n"
        "- Gold\n"
        "- Stocks\n"
        "- Trading strategy"
    )
