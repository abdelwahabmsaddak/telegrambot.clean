from utils import normalize_symbol
from data_providers import get_asset_price
from ai_engine import ask_ai

def build_analysis(symbol: str, lang_mode: str) -> str:
    sym = normalize_symbol(symbol)
    kind, price = get_asset_price(sym)
    snap = f"Type={kind}, Symbol={sym}, Price~{price}"
    user_prompt = (
        f"Analyze {sym}. Use the snapshot:\n{snap}\n\n"
        "Return:\n"
        "1) Brief summary\n2) Trend guess (short/medium)\n3) Key levels (support/resistance approx)\n"
        "4) Risk notes\n"
        "Keep it clear and practical."
    )
    return ask_ai(user_prompt, lang_mode=lang_mode, extra_context=f"Market snapshot: {snap}")

def build_signal(symbol: str, lang_mode: str, risk_pct: float) -> str:
    sym = normalize_symbol(symbol)
    kind, price = get_asset_price(sym)
    snap = f"Type={kind}, Symbol={sym}, Price~{price}, UserRisk={risk_pct}%"
    user_prompt = (
        f"Create a trade idea (NOT financial advice) for {sym} using:\n{snap}\n\n"
        "Output:\n"
        "- Bias: Buy/Sell/Hold (or Wait)\n"
        "- Entry idea (approx)\n"
        "- Stop Loss (approx)\n"
        "- Take Profit 1/2 (approx)\n"
        "- Risk management guidance for the user's risk%\n"
        "Important: clearly state it's educational and suggest paper trading."
    )
    return ask_ai(user_prompt, lang_mode=lang_mode, extra_context=f"Market snapshot: {snap}")
