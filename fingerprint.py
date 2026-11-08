"""
Turns a Telegram message into a set of "match keys".

Two messages are treated as the same content if they share at least one key.
Using several keys per message catches the common ways content is copied:
  - forwarded (same original post id)
  - re-sent with the same file (same document/photo id)
  - re-uploaded file (same size + mime type + duration)
  - same text / caption (normalized: links, @mentions, emojis, punctuation removed)
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from telethon import types

URL_RE = re.compile(r"(https?://\S+|www\.\S+|t\.me/\S+)", re.I)
MENTION_RE = re.compile(r"@\w+")
# Captions shorter than this are too generic ("Episode 1") to prove two media posts are the same
MIN_CAPTION_MATCH_LEN = 20


@dataclass
class MsgInfo:
    msg_id: int
    date: str
    kind: str
    preview: str
    file_name: str = ""
    size: int = 0
    keys: set = field(default_factory=set)


def normalize_text(text: str) -> str:
    text = URL_RE.sub(" ", text or "")
    text = MENTION_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text).lower()
    # Drop punctuation, symbols and emojis; keep letters (incl. Hindi matras), digits, spaces
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] in ("L", "M", "N", "Z"))
    return " ".join(text.split())


def _h(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def message_kind(msg) -> str:
    if msg.photo:
        return "photo"
    if msg.video_note:
        return "round_video"
    if msg.gif:
        return "gif"
    if msg.video:
        return "video"
    if msg.voice:
        return "voice"
    if msg.audio:
        return "audio"
    if msg.sticker:
        return "sticker"
    if msg.document:
        return "document"
    if msg.poll:
        return "poll"
    if msg.geo:
        return "location"
    if msg.contact:
        return "contact"
    if msg.message:
        return "text"
    return "other"


def _poll_question(msg) -> str:
    q = msg.poll.poll.question
    return getattr(q, "text", q) or ""


def fingerprint(msg, channel_id: int):
    """Return MsgInfo for a message, or None for service/empty messages."""
    if isinstance(msg, types.MessageService) or msg.action:
        return None

    kind = message_kind(msg)
    text = msg.message or ""
    norm = normalize_text(text)
    keys = set()
    file_name, size = "", 0

    # The post itself, so forwards of it in the other channel match
    keys.add(f"post:{channel_id}:{msg.id}")
    fwd = msg.fwd_from
    if fwd and isinstance(fwd.from_id, types.PeerChannel) and fwd.channel_post:
        keys.add(f"post:{fwd.from_id.channel_id}:{fwd.channel_post}")

    if msg.photo:
        keys.add(f"photo:{msg.photo.id}")
        for s in msg.photo.sizes or []:
            if isinstance(s, types.PhotoStrippedSize):
                # Tiny inline thumbnail; identical images usually produce identical bytes
                keys.add(f"thumb:{hashlib.sha1(s.bytes).hexdigest()[:16]}")
    elif msg.document:
        doc = msg.document
        keys.add(f"doc:{doc.id}")
        f = msg.file
        size = doc.size or 0
        file_name = (f.name or "") if f else ""
        duration = (f.duration or "") if f else ""
        if size:
            keys.add(f"file:{size}:{doc.mime_type}:{duration}")
    elif msg.poll:
        keys.add(f"poll:{_h(normalize_text(_poll_question(msg)))}")
    elif msg.geo:
        keys.add(f"geo:{round(msg.geo.lat, 5)}:{round(msg.geo.long, 5)}")
    elif msg.contact:
        keys.add(f"contact:{msg.contact.phone_number}")

    if norm:
        is_media = kind not in ("text", "poll", "location", "contact", "other")
        if not is_media:
            keys.add(f"text:{_h(norm)}")
        elif len(norm) >= MIN_CAPTION_MATCH_LEN:
            keys.add(f"caption:{kind}:{_h(norm)}")

    if kind == "other" and len(keys) == 1:
        return None  # nothing comparable (e.g. dice, game)

    if kind == "poll":
        preview = "📊 " + _poll_question(msg)
    else:
        preview = text or file_name or f"[{kind}]"
    preview = " ".join(preview.split())
    if len(preview) > 120:
        preview = preview[:117] + "..."

    return MsgInfo(
        msg_id=msg.id,
        date=msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "",
        kind=kind,
        preview=preview,
        file_name=file_name,
        size=size,
        keys=keys,
    )
