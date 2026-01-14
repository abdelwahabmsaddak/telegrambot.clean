import sqlite3

DB = "bot.db"

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'auto',
            platform TEXT DEFAULT 'binance',
            risk REAL DEFAULT 1.0
        )
        """)
        con.commit()

def set_user(user_id: int, **kwargs):
    init_db()
    with sqlite3.connect(DB) as con:
        con.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        for k, v in kwargs.items():
            con.execute(f"UPDATE users SET {k}=? WHERE user_id=?", (v, user_id))
        con.commit()

def get_user(user_id: int) -> dict:
    init_db()
    with sqlite3.connect(DB) as con:
        con.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        row = con.execute("SELECT lang, platform, risk FROM users WHERE user_id=?", (user_id,)).fetchone()
    return {"lang": row[0], "platform": row[1], "risk": row[2]}
