# utils.py
import re

_BIDI_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def sanitize_text(s: str) -> str:
    if not s:
        return ""
    s = _BIDI_RE.sub("", s)
    s = _CTRL_RE.sub("", s)
    return s.strip()

def detect_lang_auto(text: str) -> str:
    if re.search(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text or ""):
        return "ar"
    return "en"
