import random

def analyze_asset(asset: str) -> str:
    price = get_fake_price(asset)
    rsi = random.randint(35, 70)

    trend = "صاعد 📈" if rsi < 65 else "متذبذب ⚖️"

    return (
        f"📊 تحليل {asset}\n\n"
        f"السعر: {price}$\n"
        f"RSI: {rsi}\n"
        f"الترند: {trend}\n\n"
        "🎯 السيناريو:\n"
        "- شراء تدريجي عند التصحيحات\n"
        "- وقف خسارة أسفل الدعم\n"
        "- لا تفرط في المخاطرة ⚠️"
    )

def get_fake_price(asset):
    prices = {
        "BTC": 43120,
        "ETH": 2320,
        "XAU": 2035,
        "TSLA": 215
    }
    return prices.get(asset, 0)
