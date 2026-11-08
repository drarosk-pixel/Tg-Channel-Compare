"""Settings loaded from .env (or hosting environment variables) and a shared Telethon client factory."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
PHONE = os.getenv("PHONE", "").strip()
# For hosting: paste the string printed by `python login.py`. If set, no session file is needed.
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
SESSION_NAME = os.getenv("SESSION_NAME", "sessions/userbot").strip()
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "0") or 0)
REPORTS_DIR = os.getenv("REPORTS_DIR", "reports").strip()


def make_client(use_string=True):
    """Create a Telethon client for the user account (not a bot)."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    if not API_ID.isdigit() or not API_HASH:
        sys.exit("API_ID / API_HASH missing. Get them from https://my.telegram.org")

    if use_string and SESSION_STRING:
        session = StringSession(SESSION_STRING)
    else:
        session_dir = os.path.dirname(SESSION_NAME)
        if session_dir:
            os.makedirs(session_dir, exist_ok=True)
        session = SESSION_NAME

    # Telethon sleeps automatically on FloodWait errors shorter than this many seconds.
    return TelegramClient(session, int(API_ID), API_HASH, flood_sleep_threshold=120)
