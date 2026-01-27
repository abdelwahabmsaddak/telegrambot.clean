import os, math
from typing import Dict, List, Optional, Tuple
import ccxt
import httpx

def make_exchange(name: str):
    name = (name or "bybit").lower().strip()
    if not hasattr(ccxt, name):
        raise ValueError(f"Exchange not supported: {name}")
    ex_class = getattr(ccxt, name)
    return ex_class({"enableRateLimit": True})

def fetch_ohlcv(exchange: str, symbol: str, timeframe: str, limit: int):
    ex = make_exchange(exchange)
    markets = ex.load_markets()
    if symbol not in markets:
        # Try common formatting: BTC -> BTC/USDT
        if "/" not in symbol:
            guess = f"{symbol}/USDT"
            if guess in markets:
                symbol = guess
        if symbol not in markets:
            raise ValueError(f"Symbol not found on {exchange}: {symbol}")
    return ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit), symbol

def list_usdt_symbols(exchange: str) -> List[str]:
    ex = make_exchange(exchange)
    markets = ex.load_markets()
    out = []
    for s, m in markets.items():
        if m.get("active") and isinstance(s, str) and s.endswith("/USDT"):
            out.append(s)
    return out

def fetch_ticker(exchange: str, symbol: str) -> Dict:
    ex = make_exchange(exchange)
    ex.load_markets()
    if "/" not in symbol:
        guess = f"{symbol}/USDT"
        symbol = guess
    return ex.fetch_ticker(symbol)

# -------- WhaleAlert (optional) --------
async def whale_alert_latest(api_key: str, limit: int = 5) -> List[Dict]:
    if not api_key:
        return []
    url = "https://api.whale-alert.io/v1/transactions"
    params = {"api_key": api_key, "min_value": 500000, "limit": limit, "currency": "usd"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        return data.get("transactions", [])

# -------- OpenAI (optional) --------
async def ai_chat(prompt: str) -> Optional[str]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=key)
        resp = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a concise trading assistant. Ask short clarifying questions when needed."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception:
        return None
