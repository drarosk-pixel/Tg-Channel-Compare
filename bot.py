"""
Multi-user control bot.

Each user logs in through the bot itself (phone + OTP, optional 2FA), so no
session string is ever pasted anywhere public. Sessions are stored encrypted,
one per Telegram user, and every comparison runs on that user's own account.

Commands (in a private chat with the bot):
  /start, /help       show help
  /login              log in your account (phone -> OTP -> 2FA if set)
  /cancel             abort an in-progress login
  /status             show whether you are logged in
  /logout             delete your stored session
  /compare A B [N]    compare two channels (latest N posts each; omit N = all)

Run:  python bot.py
"""

import asyncio
import html
import logging
import re
import time

from telethon import events
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    RPCError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from comparer import compare_channels
from config import (
    ALLOWED_USER_IDS,
    BOT_TOKEN,
    DEFAULT_LIMIT,
    REPORTS_DIR,
    make_bot,
    make_user_client,
)
from report import telegram_summary, write_reports
from resolver import ResolveError, resolve_channel
from user_store import UserStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

bot = make_bot()
store = UserStore()

# user_id -> dict(step, client, phone, phone_code_hash, expires)
pending = {}
# user_ids with a comparison currently running
busy = set()

LOGIN_TIMEOUT = 600  # seconds to finish a login before it is cancelled
COMPARE_RE = re.compile(r"^/compare(?:@\w+)?\s+(\S+)\s+(\S+)(?:\s+(\d+))?\s*$", re.I)

HELP = """<b>Channel Compare Bot</b>

I compare two Telegram channels and tell you what is missing in each, with links to the posts. The comparison runs on <b>your own account</b>, so I can read any channel you are a member of.

<b>Step 1 — log in (once)</b>
<code>/login</code> then send your phone, the OTP, and your 2-step password if you have one.

<b>Step 2 — compare</b>
<code>/compare A B</code> — full history
<code>/compare A B 500</code> — only the latest 500 posts of each

A / B can be:
• <code>@username</code> or <code>https://t.me/username</code>
• <code>https://t.me/+InviteHash</code> (you must be a member)
• <code>https://t.me/c/1234567890/1</code> or <code>-1001234567890</code>

Other: <code>/status</code>, <code>/logout</code>, <code>/cancel</code>

⚠️ Logging in gives this bot full read access to your account. Only continue if you trust its operator. Use <code>/logout</code> anytime to remove your session."""


def allowed(user_id: int) -> bool:
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS


async def _cleanup(user_id):
    """Disconnect and drop a half-finished login."""
    data = pending.pop(user_id, None)
    if data and data.get("client"):
        try:
            await data["client"].disconnect()
        except Exception:
            pass


async def expire_logins():
    """Background task: drop logins that sat idle too long."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        for uid in [u for u, d in pending.items() if d["expires"] < now]:
            await _cleanup(uid)
            try:
                await bot.send_message(uid, "⌛ Login timed out. Send /login to start again.")
            except Exception:
                pass


@bot.on(events.NewMessage(pattern=r"^/(start|help)\b", func=lambda e: e.is_private))
async def on_start(event):
    if allowed(event.sender_id):
        await event.respond(HELP, parse_mode="html", link_preview=False)
    raise events.StopPropagation


@bot.on(events.NewMessage(pattern=r"^/status\b", func=lambda e: e.is_private))
async def on_status(event):
    if not allowed(event.sender_id):
        raise events.StopPropagation
    info = store.get_info(event.sender_id)
    if info:
        who = info.get("tg_name") or "your account"
        await event.respond(f"✅ Logged in as <b>{html.escape(who)}</b> "
                            f"({html.escape(info.get('phone') or '')}).\nUse /compare or /logout.",
                            parse_mode="html")
    else:
        await event.respond("You are not logged in. Send /login to start.")
    raise events.StopPropagation


@bot.on(events.NewMessage(pattern=r"^/logout\b", func=lambda e: e.is_private))
async def on_logout(event):
    if not allowed(event.sender_id):
        raise events.StopPropagation
    await _cleanup(event.sender_id)
    removed = store.delete_session(event.sender_id)
    await event.respond("🗑 Session deleted." if removed else "You were not logged in.")
    raise events.StopPropagation


@bot.on(events.NewMessage(pattern=r"^/cancel\b", func=lambda e: e.is_private))
async def on_cancel(event):
    if not allowed(event.sender_id):
        raise events.StopPropagation
    if event.sender_id in pending:
        await _cleanup(event.sender_id)
        await event.respond("Login cancelled.")
    else:
        await event.respond("Nothing to cancel.")
    raise events.StopPropagation


@bot.on(events.NewMessage(pattern=r"^/login\b", func=lambda e: e.is_private))
async def on_login(event):
    uid = event.sender_id
    if not allowed(uid):
        await event.respond("You are not allowed to use this bot.")
        raise events.StopPropagation
    if uid in pending:
        await event.respond("A login is already in progress. Send the requested value, or /cancel.")
        raise events.StopPropagation
    if store.get_session(uid):
        await event.respond("You are already logged in. Use /logout first to switch accounts.")
        raise events.StopPropagation
    pending[uid] = {"step": "phone", "client": None, "phone": None,
                    "phone_code_hash": None, "expires": time.time() + LOGIN_TIMEOUT}
    await event.respond(
        "📱 Send your phone number with country code, e.g. <code>+919876543210</code>.\n\n"
        "Send /cancel to stop.", parse_mode="html")
    raise events.StopPropagation


@bot.on(events.NewMessage(pattern=r"^/compare\b", func=lambda e: e.is_private))
async def on_compare(event):
    uid = event.sender_id
    if not allowed(uid):
        raise events.StopPropagation
    m = COMPARE_RE.match(event.raw_text or "")
    if not m:
        await event.respond("Usage: <code>/compare A B</code> or <code>/compare A B 500</code>",
                            parse_mode="html")
        raise events.StopPropagation
    session = store.get_session(uid)
    if not session:
        await event.respond("Please /login first.")
        raise events.StopPropagation
    if uid in busy:
        await event.respond("⏳ Your previous comparison is still running. Please wait.")
        raise events.StopPropagation

    raw_a, raw_b, raw_limit = m.groups()
    limit = int(raw_limit) if raw_limit else DEFAULT_LIMIT
    busy.add(uid)
    try:
        await run_compare(event, uid, session, raw_a, raw_b, limit)
    finally:
        busy.discard(uid)
    raise events.StopPropagation


async def run_compare(event, uid, session, raw_a, raw_b, limit):
    status = await event.respond("🔎 Connecting to your account…")
    client = make_user_client(session)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            store.delete_session(uid)
            await status.edit("❌ Your session expired. Send /login again.")
            return

        try:
            entity_a = await resolve_channel(client, raw_a)
            entity_b = await resolve_channel(client, raw_b)
        except (ResolveError, RPCError) as err:
            await status.edit(f"❌ {html.escape(str(err))}", parse_mode="html")
            return

        last_edit = 0.0

        async def progress(name, count):
            nonlocal last_edit
            if time.monotonic() - last_edit < 4:
                return
            last_edit = time.monotonic()
            try:
                await status.edit(f"📥 Scanning <b>{html.escape(name)}</b>: {count} messages…",
                                  parse_mode="html")
            except RPCError:
                pass

        try:
            result = await compare_channels(client, entity_a, entity_b, limit, progress)
        except FloodWaitError as err:
            await status.edit(f"❌ Telegram rate limit: wait {err.seconds}s and try again.")
            return

        html_path, csv_path = write_reports(result, REPORTS_DIR)
        await status.edit(telegram_summary(result), parse_mode="html", link_preview=False)
        await bot.send_file(event.chat_id, [html_path, csv_path],
                            caption="📄 Full report (open the HTML file for every link)")
        log.info("compare for %s: %s vs %s", uid, result.a.name, result.b.name)
    finally:
        await client.disconnect()


@bot.on(events.NewMessage(func=lambda e: e.is_private and not (e.raw_text or "").startswith("/")))
async def on_conversation(event):
    """Handles the phone / OTP / password replies during /login."""
    uid = event.sender_id
    data = pending.get(uid)
    if not data:
        return  # not in a login flow; ignore
    data["expires"] = time.time() + LOGIN_TIMEOUT
    text = (event.raw_text or "").strip()

    if data["step"] == "phone":
        await _handle_phone(event, uid, data, text)
    elif data["step"] == "code":
        await _handle_code(event, uid, data, text)
    elif data["step"] == "password":
        await _handle_password(event, uid, data, text)


async def _handle_phone(event, uid, data, text):
    phone = re.sub(r"[\s-]", "", text)
    if not re.fullmatch(r"\+\d{7,15}", phone):
        await event.respond("That doesn't look right. Send like <code>+919876543210</code>.",
                            parse_mode="html")
        return
    client = make_user_client("")
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
    except PhoneNumberInvalidError:
        await client.disconnect()
        await event.respond("❌ Invalid phone number. Try /login again.")
        await _cleanup(uid)
        return
    except FloodWaitError as err:
        await client.disconnect()
        await event.respond(f"❌ Too many attempts. Wait {err.seconds}s, then /login.")
        await _cleanup(uid)
        return
    except RPCError as err:
        await client.disconnect()
        await event.respond(f"❌ {html.escape(str(err))}", parse_mode="html")
        await _cleanup(uid)
        return

    data.update(step="code", client=client, phone=phone, phone_code_hash=sent.phone_code_hash)
    await event.respond(
        "💬 I sent an OTP to your Telegram app.\n\n"
        "Type it with spaces between the digits, e.g. <code>1 2 3 4 5</code>, so Telegram "
        "does not auto-expire it.\n\nSend /cancel to stop.", parse_mode="html")


async def _handle_code(event, uid, data, text):
    code = re.sub(r"\D", "", text)
    if len(code) < 5:
        await event.respond("Send the full OTP, digits spaced out like <code>1 2 3 4 5</code>.",
                            parse_mode="html")
        return
    client = data["client"]
    try:
        await client.sign_in(phone=data["phone"], code=code,
                            phone_code_hash=data["phone_code_hash"])
    except SessionPasswordNeededError:
        data["step"] = "password"
        await event.respond("🔐 Your account has 2-step verification. Send your password.")
        return
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        await event.respond("❌ Wrong or expired code. Send it again, or /cancel and /login afresh.")
        return
    except FloodWaitError as err:
        await event.respond(f"❌ Too many attempts. Wait {err.seconds}s, then /login.")
        await _cleanup(uid)
        return
    await _finish_login(event, uid, data)


async def _handle_password(event, uid, data, text):
    client = data["client"]
    try:
        await client.sign_in(password=text)
    except PasswordHashInvalidError:
        await event.respond("❌ Wrong password. Send it again, or /cancel.")
        return
    except FloodWaitError as err:
        await event.respond(f"❌ Too many attempts. Wait {err.seconds}s, then /login.")
        await _cleanup(uid)
        return
    await _finish_login(event, uid, data)


async def _finish_login(event, uid, data):
    client = data["client"]
    try:
        me = await client.get_me()
        name = " ".join(filter(None, [me.first_name, me.last_name])) or str(me.id)
        session_string = StringSession.save(client.session)
        store.save_session(uid, session_string, phone=data["phone"] or "", tg_name=name)
    except Exception as err:
        await event.respond(f"❌ Login failed: {html.escape(str(err))}", parse_mode="html")
        await _cleanup(uid)
        return
    await _cleanup(uid)
    await event.respond(
        f"✅ Logged in as <b>{html.escape(name)}</b>.\n\n"
        "Now try <code>/compare @channelA @channelB</code>.", parse_mode="html")


async def main():
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    asyncio.create_task(expire_logins())
    log.info("Bot @%s running. %d stored session(s).", me.username, store.count())
    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
