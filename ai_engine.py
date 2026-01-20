# ai_engine.py
import os
from openai import OpenAI
from utils import sanitize_text

class AIEngine:
    def __init__(self):
        key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.client = OpenAI(api_key=key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        self.sys_ar = (
            "أنت مساعد تداول محترف داخل بوت تيليغرام.\n"
            "القواعد:\n"
            "- اكتب بالعربية فقط.\n"
            "- اعطِ تحليلًا تعليميًا + إدارة مخاطر.\n"
            "- لا تعد بربح مضمون.\n"
            "- إذا طلب المستخدم تنفيذ صفقة: وضّح أن التنفيذ Live اختياري ويحتاج تفعيل من العميل.\n"
            "- في التحليل: سعر حي + اتجاه + دعم/مقاومة + سيناريو صعود/هبوط + مخاطرة.\n"
            "واختم بـ: هذا ليس نصيحة مالية.\n"
        )

        self.sys_en = (
            "You are a professional trading assistant inside a Telegram bot.\n"
            "Rules:\n"
            "- Reply in English only.\n"
            "- Provide educational analysis + risk management.\n"
            "- No guaranteed profits.\n"
            "- If user asks to execute trades: explain Live execution is optional and must be enabled by the user.\n"
            "In analysis: live price + trend + S/R + bull/bear scenarios + risk.\n"
            "End with: Not financial advice.\n"
        )

    def answer(self, lang: str, user_text: str, context_hint: str = "") -> str:
        lang = "ar" if lang == "ar" else "en"
        user_text = sanitize_text(user_text)
        context_hint = sanitize_text(context_hint)

        system = self.sys_ar if lang == "ar" else self.sys_en
        if context_hint:
            if lang == "ar":
                user_text = f"سياق (بيانات حية):\n{context_hint}\n\nطلب المستخدم:\n{user_text}"
            else:
                user_text = f"Context (live data):\n{context_hint}\n\nUser request:\n{user_text}"

        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
        )
        out = getattr(resp, "output_text", "") or ""
        return sanitize_text(out) or ("حصل خطأ بسيط." if lang == "ar" else "Temporary issue.")
