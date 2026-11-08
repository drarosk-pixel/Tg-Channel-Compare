"""Settings loaded from .env (or hosting environment variables) and Telethon client factories."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()

# Multi-user control bot (from @BotFather). Users log in through THIS bot.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
# Optional: Fernet key to encrypt stored user sessions at rest (python gen_key.py).
# Leave empty to store sessions as plain text (ok for a private, self-run bot).
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "").strip()
SESSIONS_DB_PATH = os.getenv("SESSIONS_DB_PATH", "data/sessions.db").strip()
# Optional comma-separated Telegram user IDs allowed to use the bot. Empty = everyone.
ALLOWED_USER_IDS = {
    int(x) for x in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()
}

# Single-account mode (login.py / compare_cli.py / userbot.py) still uses these.
PHONE = os.getenv("PHONE", "").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
SESSION_NAME = os.getenv("SESSION_NAME", "sessions/userbot").strip()

DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "0") or 0)
REPORTS_DIR = os.getenv("REPORTS_DIR", "reports").strip()


def _require_api():
    if not API_ID.isdigit() or not API_HASH:
        sys.exit("API_ID / API_HASH missing. Get them from https://my.telegram.org")


def make_client(use_string=True):
    """Single-account user client (used by login.py, compare_cli.py, userbot.py)."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    _require_api()
    if use_string and SESSION_STRING:
        session = StringSession(SESSION_STRING)
    else:
        session_dir = os.path.dirname(SESSION_NAME)
        if session_dir:
            os.makedirs(session_dir, exist_ok=True)
        session = SESSION_NAME

    return TelegramClient(session, int(API_ID), API_HASH, flood_sleep_threshold=120)


def make_bot():
    """The control bot client. Logged in with BOT_TOKEN inside bot.py's main()."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    _require_api()
    if not BOT_TOKEN:
        sys.exit("BOT_TOKEN missing. Create a bot with @BotFather and set BOT_TOKEN.")
    # In-memory session: a bot token logs in instantly, nothing to persist.
    return TelegramClient(StringSession(), int(API_ID), API_HASH)


def make_user_client(session_string: str):
    """A per-user client built from that user's stored session string."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    _require_api()
    return TelegramClient(
        StringSession(session_string), int(API_ID), API_HASH, flood_sleep_threshold=120
    )
