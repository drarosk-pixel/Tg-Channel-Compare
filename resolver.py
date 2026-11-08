"""Turn user input (username, link, invite link, id) into a channel entity, and build message links."""

import re

from telethon import functions, types, utils

INVITE_RE = re.compile(r"(?:t\.me|telegram\.me|telegram\.dog)/(?:\+|joinchat/)([\w-]+)", re.I)
PRIVATE_POST_RE = re.compile(r"t\.me/c/(\d+)", re.I)
PUBLIC_RE = re.compile(r"(?:t\.me|telegram\.me|telegram\.dog)/(?:s/)?([A-Za-z]\w{3,})", re.I)


class ResolveError(Exception):
    pass


async def resolve_channel(client, raw: str):
    """
    Accepts:
      @username | username | https://t.me/username | https://t.me/username/123
      https://t.me/+InviteHash | https://t.me/joinchat/Hash   (you must already be a member)
      https://t.me/c/1234567890/55 | -1001234567890 | 1234567890
    The logged-in account must be able to see the channel. Nothing is joined automatically.
    """
    text = raw.strip().strip("<>")

    m = INVITE_RE.search(text)
    if m:
        invite = await client(functions.messages.CheckChatInviteRequest(hash=m.group(1)))
        if isinstance(invite, types.ChatInviteAlready):
            return invite.chat
        if isinstance(invite, types.ChatInvitePeek):
            return invite.chat
        raise ResolveError(f"Your account is not a member of {raw}. Join it first, then retry.")

    m = PRIVATE_POST_RE.search(text)
    if m:
        return await _by_numeric_id(client, int(m.group(1)), raw)

    if re.fullmatch(r"-?\d+", text):
        num = int(text)
        if str(num).startswith("-100"):
            num = int(str(num)[4:])
        return await _by_numeric_id(client, abs(num), raw)

    m = PUBLIC_RE.search(text)
    username = m.group(1) if m else text.lstrip("@")
    try:
        return await client.get_entity(username)
    except (ValueError, TypeError) as e:
        raise ResolveError(f"Channel not found: {raw} ({e})") from e


async def _by_numeric_id(client, channel_id: int, raw: str):
    peer = types.PeerChannel(channel_id)
    try:
        return await client.get_entity(peer)
    except ValueError:
        # Entity not in the local cache yet: load dialogs once, then retry.
        await client.get_dialogs()
        try:
            return await client.get_entity(peer)
        except ValueError as e:
            raise ResolveError(
                f"Channel {raw} not found in your chats. Make sure this account is a member."
            ) from e


def message_link(entity, msg_id: int) -> str:
    username = getattr(entity, "username", None)
    if not username and getattr(entity, "usernames", None):
        active = [u.username for u in entity.usernames if u.active]
        username = active[0] if active else None
    if username:
        return f"https://t.me/{username}/{msg_id}"
    # Private channel link: opens only for accounts that are members
    return f"https://t.me/c/{entity.id}/{msg_id}"


def display_name(entity) -> str:
    title = getattr(entity, "title", None) or utils.get_display_name(entity)
    username = getattr(entity, "username", None)
    return f"{title} (@{username})" if username else f"{title} (private)"
