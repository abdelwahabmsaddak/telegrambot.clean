import os
from openai import OpenAI
from utils import detect_lang

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_AR = (
    "أنت مساعد تداول محترف مثل ChatGPT لكن متخصص بالأسواق (كريبتو/أسهم/ذهب). "
    "أجب بالعربية فقط. "
    "قدّم: ملخص، تحليل، سيناريوهات، إدارة مخاطر، وتحذير واضح. "
    "لا تعد بأرباح ولا تعطي أوامر تنفيذ مضمونة. "
    "إذا طلب المستخدم تداول آلي: اقترح Paper Trading أولاً."
)

SYSTEM_EN = (
    "You are a professional trading assistant (crypto/stocks/gold), ChatGPT-style. "
    "Reply in English only. "
    "Provide: summary, analysis, scenarios, risk management, and clear warnings. "
    "No profit promises and no guaranteed trade commands. "
    "If user asks for automation: suggest paper trading first."
)

def ask_ai(user_text: str, lang_mode: str = "auto", extra_context: str = "") -> str:
    if not user_text:
        return ""
    if lang_mode == "auto":
        lang = detect_lang(user_text)
    else:
        lang = lang_mode

    system = SYSTEM_AR if lang == "ar" else SYSTEM_EN

    messages = [
        {"role": "system", "content": system},
    ]
    if extra_context:
        messages.append({"role": "system", "content": extra_context})
    messages.append({"role": "user", "content": user_text})

    r = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        temperature=0.6,
        max_tokens=900,
    )
    return (r.choices[0].message.content or "").strip()
