import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def detect_lang(text: str):
    # عربي لو فيه حروف عربية
    for c in text:
        if '\u0600' <= c <= '\u06FF':
            return "ar"
    return "en"

def ai_chat(user_text: str):
    lang = detect_lang(user_text)

    if lang == "ar":
        system_prompt = (
            "أنت مساعد تداول ذكي ومحترف. "
            "تجيب بالعربية فقط. "
            "اشرح بوضوح وبأسلوب بسيط. "
            "إذا كان السؤال عن التداول، العملات، الأسهم أو الذهب أجب بدقة."
        )
    else:
        system_prompt = (
            "You are a professional AI trading assistant. "
            "Reply in English only. "
            "Explain clearly and simply."
        )

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content.strip()
