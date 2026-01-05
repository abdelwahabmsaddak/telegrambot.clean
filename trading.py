def trade_signal(asset: str) -> str:
    return (
        f"📌 إشارة تداول {asset}\n\n"
        "🟢 BUY\n"
        "🎯 TP: +2%\n"
        "⛔ SL: -1.5%\n"
        "⚠️ إدارة رأس المال ضرورية"
    )
