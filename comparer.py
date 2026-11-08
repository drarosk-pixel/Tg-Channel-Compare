"""Scan two channels with the user account and find content missing from each side."""

import time
from collections import Counter
from dataclasses import dataclass, field

from fingerprint import fingerprint
from resolver import display_name, message_link


@dataclass
class ChannelScan:
    entity: object
    name: str
    messages: list = field(default_factory=list)  # list[MsgInfo]
    skipped: int = 0

    @property
    def key_set(self):
        keys = set()
        for m in self.messages:
            keys |= m.keys
        return keys


@dataclass
class MissingItem:
    msg_id: int
    date: str
    kind: str
    preview: str
    file_name: str
    link: str  # where the content IS present


@dataclass
class CompareResult:
    a: ChannelScan
    b: ChannelScan
    missing_in_b: list  # present in A, not in B
    missing_in_a: list  # present in B, not in A
    common: int
    seconds: float

    @staticmethod
    def kind_counts(items):
        return Counter(i.kind for i in items)


async def scan_channel(client, entity, limit=0, progress=None) -> ChannelScan:
    """Read channel history. limit=0 means the whole history."""
    scan = ChannelScan(entity=entity, name=display_name(entity))
    count = 0
    async for msg in client.iter_messages(entity, limit=limit or None):
        count += 1
        info = fingerprint(msg, entity.id)
        if info is None:
            scan.skipped += 1
        else:
            scan.messages.append(info)
        if progress and count % 200 == 0:
            await progress(scan.name, count)
    if progress:
        await progress(scan.name, count)
    scan.messages.reverse()  # oldest first in reports
    return scan


def _missing(src: ChannelScan, other_keys: set):
    out = []
    for m in src.messages:
        if not (m.keys & other_keys):
            out.append(MissingItem(m.msg_id, m.date, m.kind, m.preview, m.file_name,
                                   message_link(src.entity, m.msg_id)))
    return out


async def compare_channels(client, entity_a, entity_b, limit=0, progress=None) -> CompareResult:
    start = time.monotonic()
    a = await scan_channel(client, entity_a, limit, progress)
    b = await scan_channel(client, entity_b, limit, progress)
    missing_in_b = _missing(a, b.key_set)
    missing_in_a = _missing(b, a.key_set)
    common = len(a.messages) - len(missing_in_b)
    return CompareResult(a, b, missing_in_b, missing_in_a, common, time.monotonic() - start)
