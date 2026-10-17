import html
import json
import os
import re
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()
feedparser.USER_AGENT = "KeshavNewsDigest/1.0 (+https://mishrakeshav.in)"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS") or 24)
MAX_SUMMARY_ITEMS = int(os.environ.get("MAX_SUMMARY_ITEMS") or 8)
MAX_PER_SOURCE = int(os.environ.get("MAX_PER_SOURCE") or 3)

FEEDS = {
    "Lobsters":       "https://lobste.rs/rss",
    "Simon Willison": "https://simonwillison.net/atom/everything/",
    "TechCrunch AI":  "https://techcrunch.com/category/artificial-intelligence/feed/",
}

NO_SUMMARY = {"Lobsters"}

# Next to this script, not wherever the terminal happens to be.
SEEN_FILE = Path(__file__).parent / "seen.json"
SEEN_LIMIT = 500


def load_seen():
    if not SEEN_FILE.exists():
        return []
    return json.loads(SEEN_FILE.read_text(encoding="utf-8"))


def save_seen(links):
    # Write to a temp file, then swap it in, so a crash mid-write
    # can never leave a half-written (corrupt) seen.json behind.
    links = list(dict.fromkeys(links))[-SEEN_LIMIT:]
    temp = SEEN_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(links, indent=2), encoding="utf-8")
    os.replace(temp, SEEN_FILE)


def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def collect_entries():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items = []
    problems = []

    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        status = feed.get("status")
        if status is None or status >= 400 or len(feed.entries) == 0:
            reason = feed.get("bozo_exception", "")
            problem = f"{source}: status {status}, {len(feed.entries)} entries {reason}".strip()
            print(f"  WARNING: {problem}")
            problems.append(problem)
            continue

        for entry in feed.entries:
            when = entry.get("published_parsed")
            if when is None:
                continue

            published = datetime(*when[:6], tzinfo=timezone.utc)
            if published < cutoff:
                continue

            if source in NO_SUMMARY:
                summary = ""
            else:
                summary = strip_html(entry.get("summary", ""))[:200]

            items.append({
                "source": source,
                "title": entry.get("title", "(no title)"),
                "link": entry.get("link", ""),
                "summary": summary,
                "published": published,
            })

    items.sort(key=lambda x: x["published"], reverse=True)
    return items, problems


def split_tiers(items):
    """Newest-first into the top tier, at most MAX_PER_SOURCE per source.
    Everything that doesn't fit goes to "Also today" — nothing is dropped."""
    top, rest = [], []
    per_source = {}

    for item in items:
        count = per_source.get(item["source"], 0)
        if len(top) < MAX_SUMMARY_ITEMS and count < MAX_PER_SOURCE:
            top.append(item)
            per_source[item["source"]] = count + 1
        else:
            rest.append(item)

    return top, rest


def link_html(item):
    link = html.escape(item["link"], quote=True)
    return f"<a href=\"{link}\">{html.escape(item['title'])}</a>"


def build_message(items, problems):
    top, rest = split_tiers(items)
    lines = [f"<b>Tech digest — {datetime.now().strftime('%d %b')}</b>", ""]

    if not items:
        lines.append(f"No new stories in the last {LOOKBACK_HOURS} hours.")
        lines.append("")

    for item in top:
        lines.append(link_html(item))
        lines.append(f"<i>{html.escape(item['source'])}</i>")
        if item["summary"]:
            lines.append(html.escape(item["summary"]))
        lines.append("")

    footer = []
    if problems:
        footer.append("⚠️ <b>Feed problems:</b>")
        for problem in problems:
            footer.append(html.escape(problem))

    # Telegram rejects messages over 4096 chars. Fill "Also today" until
    # we'd cross a safe budget, then summarise what didn't fit.
    budget = 4000 - len("\n".join(lines + footer))
    also = []
    for index, item in enumerate(rest):
        line = f"• {link_html(item)} — <i>{html.escape(item['source'])}</i>"
        more = f"…and {len(rest) - index} more"
        if len("\n".join(also + [line, more])) > budget:
            also.append(more)
            break
        also.append(line)

    if also:
        lines.append("<b>Also today</b>")
        lines.extend(also)
        lines.append("")

    return "\n".join(lines + footer).strip()


def send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=30)
    print(response.status_code)
    if response.status_code != 200:
        raise RuntimeError(f"Telegram returned {response.status_code}: {response.text}")


def main():
    seen = load_seen()
    seen_set = set(seen)

    items, problems = collect_entries()
    new_items = [i for i in items if i["link"] not in seen_set]
    print(f"Found {len(items)} items from the last {LOOKBACK_HOURS} hours, "
          f"{len(new_items)} not sent before")

    send(build_message(new_items, problems))

    # Only reached if send() didn't raise — a failed send marks nothing as seen.
    save_seen(seen + [i["link"] for i in new_items])
    print(f"seen.json now holds {len(load_seen())} links")


def run():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing — fill them in .env")

    try:
        main()
    except Exception:
        error = traceback.format_exc()
        print(error)
        try:
            send(f"⚠️ <b>Digest crashed</b>\n<pre>{html.escape(error[-3500:])}</pre>")
        except Exception as alert_error:
            print(f"Could not send crash alert either: {alert_error}")
        raise


if __name__ == "__main__":
    run()
