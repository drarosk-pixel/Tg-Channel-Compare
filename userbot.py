"""
Userbot: runs on your own Telegram account and listens for commands
that YOU type in your "Saved Messages" chat. Nobody else can trigger it.

  .compare <channelA> <channelB> [limit]
  .help

Run:  python userbot.py   (run `python login.py` once before this)
"""

import asyncio
import html
import logging
import os
import time

from telethon import events
from telethon.errors import ChannelPrivateError, FloodWaitError, RPCError

from comparer import compare_channels
from config import DEFAULT_LIMIT, REPORTS_DIR, SESSION_NAME, SESSION_STRING, make_client
from report import telegram_summary, write_reports
from resolver import ResolveError, resolve_channel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("userbot")

HELP = """<b>Channel Compare Userbot</b>

<code>.compare A B</code> – compare full history
<code>.compare A B 500</code> – only latest 500 posts of each

A / B can be:
• <code>@username</code> or <code>https://t.me/username</code>
• <code>https://t.me/+InviteHash</code> (you must be a member)
• <code>https://t.me/c/1234567890/1</code> or <code>-1001234567890</code>

Result: what is missing in B (with links to the post in A) and what is missing in A (links to B), plus an HTML + CSV report."""

COMPARE_RE = r"^\.compare\s+(\S+)\s+(\S+)(?:\s+(\d+))?\s*$"

client = make_client()
busy = asyncio.Lock()
MY_ID = None


def from_saved_messages(event) -> bool:
    return event.out and event.is_private and event.chat_id == MY_ID


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.help\s*$"))
async def on_help(event):
    if from_saved_messages(event):
        await event.reply(HELP, parse_mode="html")


@client.on(events.NewMessage(outgoing=True, pattern=COMPARE_RE))
async def on_compare(event):
    if not from_saved_messages(event):
        return
    if busy.locked():
        await event.reply("⏳ A comparison is already running. Please wait.")
        return

    async with busy:
        raw_a, raw_b, raw_limit = event.pattern_match.groups()
        limit = int(raw_limit) if raw_limit else DEFAULT_LIMIT
        status = await event.reply("🔎 Resolving channels…")

        try:
            entity_a = await resolve_channel(client, raw_a)
            entity_b = await resolve_channel(client, raw_b)
        except (ResolveError, RPCError) as err:
            await status.edit(f"❌ {err}")
            return

        last_edit = 0.0

        async def progress(name, count):
            nonlocal last_edit
            if time.monotonic() - last_edit < 4:  # avoid flood limits on edits
                return
            last_edit = time.monotonic()
            try:
                await status.edit(f"📥 Scanning <b>{html.escape(name)}</b>: {count} messages…",
                                  parse_mode="html")
            except RPCError:
                pass

        try:
            result = await compare_channels(client, entity_a, entity_b, limit, progress)
        except ChannelPrivateError:
            await status.edit("❌ One of the channels is private and this account can't read it.")
            return
        except FloodWaitError as err:
            await status.edit(f"❌ Telegram rate limit: wait {err.seconds}s and try again.")
            return

        html_path, csv_path = write_reports(result, REPORTS_DIR)
        await status.edit(telegram_summary(result), parse_mode="html", link_preview=False)
        await client.send_file("me", [html_path, csv_path],
                               caption="📄 Full report (open the HTML file for all links)")
        log.info("Done: %s vs %s -> %s", result.a.name, result.b.name, html_path)


async def main():
    global MY_ID
    if not SESSION_STRING and not os.path.exists(f"{SESSION_NAME}.session"):
        raise SystemExit("No session found. Run `python login.py` first, or set SESSION_STRING.")
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("Session expired or invalid. Run `python login.py` again.")
    me = await client.get_me()
    MY_ID = me.id
    log.info("Userbot running as %s (id %s). Type .help in Saved Messages.", me.first_name, me.id)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
