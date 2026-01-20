# ai_engine.py
# -*- coding: utf-8 -*-

import os
import re
from typing import Optional

from openai import OpenAI

# Removes invisible bidi / direction marks that often break logs/encoding
_BIDI_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    text = _BIDI_RE.sub("", text)
    return text.strip()

class AIEngine:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY env var")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")  # you can change in Railway env

        # System prompts separated by language (no mixing)
        self.system_ar = (
            "أنت مساعد تداول محترف داخل بوت تيليغرام. "
            "اكتب بالعربية فقط. "
            "قدّم شرحًا واضحًا ومنظمًا. "
            "لا تعد بربح مضمون ولا تعطي أوامر شراء/بيع إلزامية. "
            "إذا سُئلت عن (تحليل/إدارة مخاطر/استراتيجية) قدّم خطوات عملية وأمثلة. "
            "إذا طلب المستخدم قرار تداول، أعطِ سيناريوهات محتملة + مستويات مراقبة + إدارة مخاطر."
        )

        self.system_en = (
            "You are a professional trading assistant inside a Telegram bot. "
            "Write in English only. "
            "Be structured and practical. "
            "Never promise guaranteed profit. "
            "If asked for a trade decision, provide scenarios, key levels to watch, and risk management."
        )

    def _system_for_lang(self, lang: str) -> str:
        return self.system_ar if lang == "ar" else self.system_en

    def answer(self, *, lang: str, user_text: str, context_hint: Optional[str] = None) -> str:
        """
        Returns a clean AI answer in the same language requested.
        Uses OpenAI Responses API (recommended in official SDK).  1
        """
        lang = "ar" if lang == "ar" else "en"
        user_text = sanitize_text(user_text)
        context_hint = sanitize_text(context_hint or "")

        if not user_text:
            return "اكتب سؤالك." if lang == "ar" else "Please type your question."

        system = self._system_for_lang(lang)

        # Build one prompt (simple + stable)
        prompt = user_text
        if context_hint:
            if lang == "ar":
                prompt = f"معلومات سياق:\n{context_hint}\n\nسؤال المستخدم:\n{user_text}"
            else:
                prompt = f"Context:\n{context_hint}\n\nUser question:\n{user_text}"

        # Responses API
        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )

        # The SDK provides output_text for convenience
        text = getattr(resp, "output_text", "") or ""
        text = sanitize_text(text)

        if not text:
            return "صار خطأ في الرد." if lang == "ar" else "Something went wrong generating a reply."
        return text
