"""
Per-user session storage for the multi-user bot.

Each Telegram user who logs in gets ONE row: their user id, phone and a
Telethon session string. The session string grants full access to that
user's account.

Encryption is optional:
  - ENCRYPTION_KEY set   -> sessions are encrypted at rest (recommended).
  - ENCRYPTION_KEY empty -> sessions are stored as plain text (fine for a
                            private bot you run yourself for a few accounts).
"""

import logging
import os
import sqlite3
import sys
import time

from config import ENCRYPTION_KEY, SESSIONS_DB_PATH

log = logging.getLogger("user_store")


def _fernet():
    """Return a Fernet instance if a key is set, else None (plaintext mode)."""
    if not ENCRYPTION_KEY:
        log.warning("ENCRYPTION_KEY not set: user sessions are stored UNENCRYPTED in %s. "
                    "Keep that file private.", SESSIONS_DB_PATH)
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        sys.exit("ENCRYPTION_KEY is set but 'cryptography' is not installed. "
                 "Run: pip install -r requirements.txt  (or leave ENCRYPTION_KEY empty)")
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
        raw = session_string.encode()
        token = self._fernet.encrypt(raw) if self._fernet else raw
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
        if not self._fernet:
            return bytes(row["session"]).decode(errors="replace")
        try:
            return self._fernet.decrypt(row["session"]).decode()
        except Exception:
            # Wrong/rotated key, or data saved in plaintext mode: treat as not logged in.
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
