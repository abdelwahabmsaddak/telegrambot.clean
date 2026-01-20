# ai_engine.py
# -*- coding: utf-8 -*-

import os
import re
import sys
from typing import Dict, List

from openai import OpenAI  # pip install openai


# --- Force UTF-8 stdout (avoids ascii codec crashes in some hosts) ---
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# Characters that often break ASCII encoders (Arabic keyboards insert these)
_BIDI_CONTROL_CHARS = [
    "\u200e",  # LRM
    "\u200f",  # RLM
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # bidi overrides
]


def sanitize_text(s: str) -> str:
    if not s:
        return ""
    # remove bidi controls
    for ch in _BIDI_CONTROL_CHARS:
        s = s.replace(ch, "")
    # remove other invisible control chars except newline/tab
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    return s.strip()


def detect_lang_auto(text: str) -> str:
    # Very simple: if Arabic letters exist => ar else en
    if re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text or ""):
        return "ar"
    return "en"


def build_system_prompt(lang: str) -> str:
    if lang == "ar":
        return (
            "أنت مساعد تداول ذكي داخل بوت تيليجرام.\n"
            "قواعد مهمة:\n"
            "- اكتب بالعربية فقط.\n"
            "- قدّم تحليلًا تعليميًا وإدارة مخاطر، ولا تعطِ وعود ربح.\n"
            "- إذا سأل المستخدم عن تنفيذ تداول حقيقي: وضّح أنه غير مفعّل إلا إذا فعّل (Auto) "
            "وأنه افتراضيًا Paper فقط.\n"
            "- عند عدم توفر بيانات سعر لحظية، وضّح ذلك وقدّم خطوات تحليل عامة.\n"
        )
    return (
        "You are a trading assistant inside a Telegram bot.\n"
        "Rules:\n"
        "- Reply in English only.\n"
        "- Provide educational analysis and risk management. No profit promises.\n"
        "- Real trading is disabled by default (paper only) unless user enables Auto.\n"
        "- If live pricing isn't available, say so and give general analysis steps.\n"
    )


class AIEngine:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing.")
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1")  # example model in docs 1

    def chat(self, user_text: str, lang_mode: str = "auto", history: List[Dict] | None = None) -> str:
        user_text = sanitize_text(user_text)
        history = history or []

        lang = detect_lang_auto(user_text) if lang_mode == "auto" else lang_mode
        system_prompt = build_system_prompt(lang)

        # Build input messages
        input_messages = [{"role": "system", "content": system_prompt}]
        # Keep short history (optional)
        for m in history[-8:]:
            role = m.get("role", "user")
            content = sanitize_text(m.get("content", ""))
            if content:
                input_messages.append({"role": role, "content": content})
        input_messages.append({"role": "user", "content": user_text})

        try:
            # OpenAI Responses API (Python)
            resp = self.client.responses.create(
                model=self.model,
                input=input_messages,
            )
            # Most convenient text getter
            text = getattr(resp, "output_text", None)
            if text:
                return sanitize_text(text)

            # Fallback: try to extract from output list (defensive)
            out = getattr(resp, "output", []) or []
            for item in out:
                content = item.get("content") if isinstance(item, dict) else None
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                            t = c.get("text", "")
                            if t:
                                return sanitize_text(t)

            return "AI: Empty response."
        except Exception as e:
            # Return safe text without triggering ascii encoding
            err = sanitize_text(str(e))
            return f"AI Error: {err}"
