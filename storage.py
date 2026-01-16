import sqlite3
from contextlib import closing

DB_PATH = "bot.db"

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            lang_mode TEXT DEFAULT 'auto',     -- auto|ar|en
            platform TEXT DEFAULT 'binance',
            risk REAL DEFAULT 1.0,
            auto_enabled INTEGER DEFAULT 0,    -- 0/1
            auto_interval_min INTEGER DEFAULT 15,
            watchlist TEXT DEFAULT 'BTC,ETH'
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS paper_positions(
            user_id INTEGER,
            symbol TEXT,
            side TEXT,
            entry REAL,
            qty REAL,
            usd REAL,
            opened_at TEXT,
            PRIMARY KEY(user_id, symbol)
        )
        """)

        con.commit()

def get_user(user_id: int) -> dict:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()
        cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        con.commit()
        row = cur.execute("""
            SELECT lang_mode, platform, risk, auto_enabled, auto_interval_min, watchlist
            FROM users WHERE user_id=?
        """, (user_id,)).fetchone()

    return {
        "lang_mode": row[0],
        "platform": row[1],
        "risk": float(row[2]),
        "auto_enabled": int(row[3]),
        "auto_interval_min": int(row[4]),
        "watchlist": row[5] or "BTC,ETH",
    }

def update_user(user_id: int, **fields):
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()
        cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        for k, v in fields.items():
            cur.execute(f"UPDATE users SET {k}=? WHERE user_id=?", (v, user_id))
        con.commit()

def list_paper_positions(user_id: int):
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()
        rows = cur.execute("""
            SELECT symbol, side, entry, qty, usd, opened_at
            FROM paper_positions WHERE user_id=?
            ORDER BY opened_at DESC
        """, (user_id,)).fetchall()
    return rows

def upsert_paper_position(user_id: int, symbol: str, side: str, entry: float, qty: float, usd: float, opened_at: str):
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO paper_positions(user_id, symbol, side, entry, qty, usd, opened_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(user_id, symbol) DO UPDATE SET
                side=excluded.side,
                entry=excluded.entry,
                qty=excluded.qty,
                usd=excluded.usd,
                opened_at=excluded.opened_at
        """, (user_id, symbol, side, entry, qty, usd, opened_at))
        con.commit()

def delete_paper_position(user_id: int, symbol: str):
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()
        cur.execute("DELETE FROM paper_positions WHERE user_id=? AND symbol=?", (user_id, symbol))
        con.commit()
