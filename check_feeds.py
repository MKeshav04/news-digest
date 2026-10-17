import feedparser

FEEDS = {
     "Lobsters":      "https://lobste.rs/rss",
    "Simon Willison":"https://simonwillison.net/atom/everything/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Ars Technica":  "https://feeds.arstechnica.com/arstechnica/index",
}

for name, url in FEEDS.items():
    print("=" * 60)
    print(f"SOURCE: {name}")

    feed = feedparser.parse(url)

    print(f"    entries found: {len(feed.entries)}")

    if len(feed.entries)  == 0:
        print("  **NOTHING CAME BACK - Feed is broken or blocked **")
        continue

    first = feed.entries[0]

    print(f"  title:    {first.title}")
    print(f"  link:     {first.link}")
    print(f"  published:{first.get('published', 'NO DATE FIELD')}")

    description = first.get("summary", "")
    print(f"  description length: {len(description)} characters")
    print(f"  description preview: {description[:150]}")