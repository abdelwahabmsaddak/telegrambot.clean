# ai_engine.py
# -*- coding: utf-8 -*-

import os
import re
from openai import OpenAI

# =========================
# OpenAI Client
# =========================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# Text Cleaner (VERY IMPORTANT)
# =========================
def clean_text(text: str) -> str:
    if not text:
        return ""
    # remove hidden RTL/LTR characters that break ascii
    text = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', text)
    return text.strip()

# =========================
# AI Chat Function
# =========================
def ai_chat(user_message: str, lang: str = "auto") -> str:
    try:
        user_message = clean_text(user_message)

        system_prompt_ar = (
            "أنت مساعد تداول ذكي ومحترف. "
            "تجيب باللغة العربية فقط. "
            "تقدم تحليل عملات رقمية، أسهم، ذهب، إدارة مخاطر، "
            "وتنبيه أن المعلومات تعليمية وليست نصيحة استثمارية."
        )

        system_prompt_en = (
            "You are a professional AI trading assistant. "
            "Reply in English only. "
            "Provide crypto, stocks, gold analysis and risk management. "
            "Educational only, not financial advice."
        )

        if lang == "ar":
            system_prompt = system_prompt_ar
        elif lang == "en":
            system_prompt = system_prompt_en
        else:
            system_prompt = system_prompt_ar + " / " + system_prompt_en

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.6,
            max_tokens=700
        )

        reply = response.choices[0].message.content
        reply = clean_text(reply)

        return reply

    except Exception as e:
        return f"❌ AI Error: {str(e)}"
