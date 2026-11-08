"""
Run a comparison from the terminal without Telegram commands.

  python compare_cli.py @channelA https://t.me/+InviteHashB
  python compare_cli.py @channelA @channelB --limit 500
"""

import argparse
import asyncio

from comparer import compare_channels
from config import DEFAULT_LIMIT, REPORTS_DIR, make_client
from report import write_reports
from resolver import ResolveError, resolve_channel


async def main():
    p = argparse.ArgumentParser(description="Compare two Telegram channels")
    p.add_argument("channel_a")
    p.add_argument("channel_b")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="latest N posts per channel (0 = all)")
    args = p.parse_args()

    client = make_client()
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("Not logged in. Run `python login.py` first.")

    try:
        a = await resolve_channel(client, args.channel_a)
        b = await resolve_channel(client, args.channel_b)
    except ResolveError as err:
        raise SystemExit(f"Error: {err}")

    async def progress(name, count):
        print(f"\rScanning {name}: {count} messages", end="", flush=True)

    result = await compare_channels(client, a, b, args.limit, progress)
    print()
    html_path, csv_path = write_reports(result, REPORTS_DIR)

    print(f"\nA: {result.a.name} ({len(result.a.messages)} msgs)")
    print(f"B: {result.b.name} ({len(result.b.messages)} msgs)")
    print(f"In both: {result.common}")
    for title, items in (("Missing in B", result.missing_in_b), ("Missing in A", result.missing_in_a)):
        print(f"\n{title}: {len(items)}")
        for i in items[:20]:
            print(f"  [{i.kind}] {i.preview[:60]}  ->  {i.link}")
        if len(items) > 20:
            print(f"  ...and {len(items) - 20} more")
    print(f"\nReport: {html_path}\nCSV:    {csv_path}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
