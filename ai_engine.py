import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

def ai_chat(message: str, lang: str = "auto") -> str:
    if not client.api_key:
        return "❌ OpenAI API KEY غير موجود."

    system_prompt = (
        "أنت مساعد تداول ذكي ومحترف. "
        "تجاوب بوضوح وبنفس لغة المستخدم فقط. "
        "تقدّم تحليل، إدارة مخاطر، وأفكار تداول بدون أوامر تنفيذ حقيقية."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"❌ خطأ في الذكاء الاصطناعي: {e}"
