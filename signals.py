def generate_signal(text: str) -> str:
    asset = "BTC"

    if "eth" in text.lower():
        asset = "ETH"
    elif "gold" in text.lower() or "xau" in text.lower():
        asset = "GOLD"

    return (
        f"🎯 إشارة تداول ({asset})\n\n"
        "📌 الاتجاه: شراء (Buy)\n"
        "🎯 الهدف: +2% إلى +4%\n"
        "🛑 وقف الخسارة: -1%\n"
        "⚠️ مخاطرة: متوسطة\n\n"
        "❗ هذه إشارة تعليمية وليست نصيحة مالية."
    )
