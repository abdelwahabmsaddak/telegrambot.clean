 # ai_engine.py
import os
import re
from typing import Optional

# Optional OpenAI (safe import)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# بعض رموز اتجاه النص تسبب مشاكل encoding / عرض (مثل \u200e)
_BIDI_MARKS_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = _BIDI_MARKS_RE.sub("", s)
    s = s.replace("\x00", "")
    return s.strip()


class AIEngine:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        self._client = None

        if OpenAI and self.api_key:
            try:
                self._client = OpenAI(api_key=self.api_key, timeout=self.timeout)
            except Exception:
                self._client = None

    def available(self) -> bool:
        return self._client is not None

    def chat(self, user_text: str, system_prompt: str) -> str:
        """
        Returns AI answer if available, otherwise a safe fallback.
        """
        user_text = clean_text(user_text)
        system_prompt = clean_text(system_prompt)

        # Fallback if no key / library / errors
        if not self.available():
            return self.fallback_answer(user_text)

        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.4,
                max_tokens=900,
            )
            out = resp.choices[0].message.content or ""
            out = clean_text(out)
            return out if out else self.fallback_answer(user_text)
        except Exception:
            return self.fallback_answer(user_text)

    def fallback_answer(self, user_text: str) -> str:
        # رد ثابت محترم كي API يطيح/مافيش رصيد
        return (
            "⚠️ الذكاء الاصطناعي غير متاح الآن (مفتاح/رصيد/اتصال).\n\n"
            "✅ نقدر نخدمك بالوضع الثابت:\n"
            "• Analysis + Chart\n"
            "• Signals (Paper)\n"
            "• Auto Paper تنبيهات\n\n"
            "ابعث رمز واضح مثل: BTC أو ETH أو TSLA أو XAUUSD"
        )
