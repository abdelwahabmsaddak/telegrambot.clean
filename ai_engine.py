# ai_engine.py
import os
import re
from openai import OpenAI

# Force a safe default model; you can override with env OPENAI_MODEL
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Create client once
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Remove invisible direction marks + control chars that cause encoding issues
_INVISIBLE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def sanitize_text(s: str) -> str:
    if not s:
        return ""
    s = _INVISIBLE.sub("", s)
    s = _CTRL.sub("", s)
    return s.strip()

def build_system_prompt(lang: str) -> str:
    # lang is "ar" or "en"
    if lang == "ar":
        return (
            "أنت مساعد تداول ذكي داخل بوت تيليغرام.\n"
            "القواعد:\n"
            "- جاوب بالعربية فقط.\n"
            "- قدم تحليل/تعليم وإدارة مخاطر، ولا تعد بأرباح.\n"
            "- إذا طلب المستخدم تنفيذ تداول فعلي: وضّح أنه اختياري وأنك لا تنفذ صفقات حقيقية.\n"
            "- اجعل الردود عملية: نقاط + مستويات محتملة + سيناريوهين (صعود/هبوط).\n"
            "- اذكر تنبيه: 'هذا ليس نصيحة مالية'.\n"
        )
    return (
        "You are a smart trading assistant inside a Telegram bot.\n"
        "Rules:\n"
        "- Reply in English only.\n"
        "- Provide educational analysis and risk management; no promises of profit.\n"
        "- If user asks to execute real trades: explain it is optional and you do not place real orders.\n"
        "- Be practical: bullets + possible levels + 2 scenarios (bull/bear).\n"
        "- Include: 'Not financial advice.'\n"
    )

def ai_chat(user_text: str, lang: str = "ar") -> str:
    """
    Returns AI response text (sanitized). Raises exception upward (bot.py handles it).
    Uses OpenAI Responses API. 1
    """
    user_text = sanitize_text(user_text)
    if not user_text:
        return "اكتب سؤالك." if lang == "ar" else "Type your question."

    system = build_system_prompt(lang)

    resp = _client.responses.create(
        model=DEFAULT_MODEL,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
    )

    # response.output_text is the simplest extraction method in the SDK
    out = getattr(resp, "output_text", "") or ""
    out = sanitize_text(out)

    if not out:
        # fallback
        return "حصل خطأ بسيط، جرّب مرة أخرى." if lang == "ar" else "Temporary issue, please try again."
    return out
