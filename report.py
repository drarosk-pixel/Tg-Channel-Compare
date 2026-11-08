"""Write comparison results as HTML + CSV files and a short Telegram summary."""

import csv
import html
import os
import re
from datetime import datetime

ICONS = {
    "text": "📝", "photo": "🖼", "video": "🎬", "gif": "🎞", "round_video": "⭕",
    "audio": "🎵", "voice": "🎤", "document": "📄", "sticker": "🏷", "poll": "📊",
    "location": "📍", "contact": "👤", "other": "❔",
}

e = html.escape


def _slug(name: str) -> str:
    return re.sub(r"[^\w-]+", "_", name)[:40].strip("_") or "channel"


def _counts_line(result, items):
    counts = result.kind_counts(items)
    return ", ".join(f"{ICONS.get(k, '')} {k}: {v}" for k, v in counts.most_common()) or "none"


def write_reports(result, reports_dir: str):
    """Return (html_path, csv_path)."""
    os.makedirs(reports_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(reports_dir, f"compare_{_slug(result.a.name)}_vs_{_slug(result.b.name)}_{stamp}")

    csv_path = base + ".csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["missing_in", "present_in", "message_id", "date", "type", "file_name", "preview", "link"])
        for missing_in, present_in, items in (
            (result.b.name, result.a.name, result.missing_in_b),
            (result.a.name, result.b.name, result.missing_in_a),
        ):
            for i in items:
                w.writerow([missing_in, present_in, i.msg_id, i.date, i.kind, i.file_name, i.preview, i.link])

    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_html(result))
    return html_path, csv_path


def _table(items):
    if not items:
        return "<p class='ok'>Nothing missing 🎉</p>"
    rows = "".join(
        f"<tr><td>{n}</td><td>{ICONS.get(i.kind, '')} {e(i.kind)}</td><td>{e(i.date)}</td>"
        f"<td>{e(i.preview)}</td><td><a href='{e(i.link)}' target='_blank'>Open</a></td></tr>"
        for n, i in enumerate(items, 1)
    )
    return ("<table><tr><th>#</th><th>Type</th><th>Date</th><th>Content</th><th>Link</th></tr>"
            f"{rows}</table>")


def _html(r):
    a, b = e(r.a.name), e(r.b.name)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Channel comparison</title>
<style>
body{{font-family:system-ui,sans-serif;margin:16px;color:#222}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{border:1px solid #ddd;padding:6px;text-align:left;vertical-align:top}}
th{{background:#f3f3f3}} .ok{{color:green}} .box{{background:#f7f9fc;padding:10px;border-radius:8px}}
</style></head><body>
<h1>Channel comparison</h1>
<div class="box">
<p><b>A:</b> {a} — {len(r.a.messages)} messages scanned</p>
<p><b>B:</b> {b} — {len(r.b.messages)} messages scanned</p>
<p>Present in both: {r.common} &nbsp;|&nbsp; Generated: {datetime.now():%Y-%m-%d %H:%M} &nbsp;|&nbsp; Took {r.seconds:.0f}s</p>
</div>
<h2>Missing in B ({len(r.missing_in_b)}) — links open the post in A</h2>
<p>{e(_counts_line(r, r.missing_in_b))}</p>
{_table(r.missing_in_b)}
<h2>Missing in A ({len(r.missing_in_a)}) — links open the post in B</h2>
<p>{e(_counts_line(r, r.missing_in_a))}</p>
{_table(r.missing_in_a)}
</body></html>"""


def telegram_summary(r, max_links=15) -> str:
    """HTML-formatted summary that stays under Telegram's 4096-char limit."""
    def section(title, items):
        lines = [f"\n<b>❌ {e(title)}: {len(items)}</b>"]
        if items:
            lines.append(e(_counts_line(r, items)))
            for i in items[:max_links]:
                lines.append(f"{ICONS.get(i.kind, '')} <a href=\"{e(i.link)}\">{e(i.preview[:60])}</a>")
            if len(items) > max_links:
                lines.append(f"…and {len(items) - max_links} more (see report file)")
        return lines

    parts = [
        "<b>📊 Channel comparison</b>",
        f"<b>A:</b> {e(r.a.name)} ({len(r.a.messages)} msgs)",
        f"<b>B:</b> {e(r.b.name)} ({len(r.b.messages)} msgs)",
        f"✅ In both: {r.common}",
    ]
    parts += section("Missing in B (links → A)", r.missing_in_b)
    parts += section("Missing in A (links → B)", r.missing_in_a)
    text = "\n".join(parts)
    if len(text) > 4000 and max_links > 3:
        return telegram_summary(r, max_links // 2)
    return text
