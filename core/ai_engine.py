from openai import OpenAI

client = OpenAI()

def detect_lang(text: str) -> str:
    return "ar" if any("\u0600" <= c <= "\u06FF" for c in text) else "en"

def chat_answer(user_text: str, lang: str = "auto") -> str:
    if lang == "auto":
        lang = detect_lang(user_text)

    system = (
        "أنت محلل مالي محترف. أجب بوضوح وباختصار مع نقاط عملية وإدارة مخاطرة."
        if lang == "ar"
        else "You are a professional market analyst. Answer clearly and concisely with actionable points and risk management."
    )

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
    )
    return r.choices[0].message.content
