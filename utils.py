import re

AR_RE = re.compile(r"[\u0600-\u06FF]")

def detect_lang(text: str) -> str:
    # إذا فيه عربي => ar، غير ذلك en
    return "ar" if AR_RE.search(text or "") else "en"

def normalize_symbol(sym: str) -> str:
    s = (sym or "").strip().upper()
    if s in ("GOLD", "XAU", "XAUUSD"):
        return "XAU"
    return s

def split_watchlist(w: str):
    items = []
    for x in (w or "").split(","):
        t = x.strip().upper()
        if t:
            items.append(t)
    return items or ["BTC", "ETH"]
