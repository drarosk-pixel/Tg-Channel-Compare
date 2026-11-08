"""
Per-user session storage for the multi-user bot.

Each Telegram user who logs in gets ONE row: their user id, phone and an
encrypted Telethon session string. The session string grants full access to
that user's account, so it is encrypted at rest with a Fernet key
(ENCRYPTION_KEY). Without the key the bot refuses to start.
"""

import os
import sqlite3
import sys
import time

from config import ENCRYPTION_KEY, SESSIONS_DB_PATH


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        sys.exit("cryptography not installed. Run: pip install -r requirements.txt")
    if not ENCRYPTION_KEY:
        sys.exit("ENCRYPTION_KEY missing. Generate one with: python gen_key.py")
    try:
        return Fernet(ENCRYPTION_KEY.encode())
    except Exception:
        sys.exit("ENCRYPTION_KEY is invalid. Generate a fresh one with: python gen_key.py")


class UserStore:
    def __init__(self, path: str = SESSIONS_DB_PATH):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._fernet = _fernet()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id   INTEGER PRIMARY KEY,
                    phone     TEXT,
                    tg_name   TEXT,
                    session   BLOB NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def save_session(self, user_id: int, session_string: str, phone: str = "", tg_name: str = ""):
        token = self._fernet.encrypt(session_string.encode())
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (user_id, phone, tg_name, session, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    phone=excluded.phone, tg_name=excluded.tg_name,
                    session=excluded.session, updated_at=excluded.updated_at
                """,
                (user_id, phone, tg_name, token, now, now),
            )

    def get_session(self, user_id: int):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return None
        try:
            return self._fernet.decrypt(row["session"]).decode()
        except Exception:
            # Wrong/rotated key: treat as not logged in rather than crash.
            return None

    def get_info(self, user_id: int):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, phone, tg_name, created_at, updated_at FROM sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, user_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            return cur.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
