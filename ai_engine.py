import os
import re
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

def detect_lang_auto(text: str) -> str:
    # بسيط: إذا فيه حروف عربية => ar
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    return "en"

def chat_answer(prompt: str, lang: str = "auto") -> str:
    if lang == "auto":
        lang = detect_lang_auto(prompt)

    system_ar = (
        "أنت محلل مالي محترف. قدّم تحليل وتعليمات واضحة قابلة للتنفيذ، "
        "مع إدارة مخاطر صارمة وتنبيه مخاطر. تجنّب وعود الأرباح."
    )
    system_en = (
        "You are a professional market analyst. Give clear, actionable guidance, "
        "strict risk management, and strong risk warnings. Avoid profit promises."
    )

    system = system_ar if lang == "ar" else system_en

    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=900,
    )
    return resp.choices[0].message.content.strip()
