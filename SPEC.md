# News Digest Bot — Build Spec & Handoff

> This file is the full context for building a daily tech/AI news digest bot
> that posts to Telegram. It was written after a working session where the
> fundamentals were built and tested by hand. Read it fully before writing code.

---

## 0. HOW TO WORK WITH ME (read this first)

I am Keshav. This project is a **learning project first**, a working bot second.

**My environment:**
- **Windows.** Always give Windows / PowerShell commands. Never give Mac or
  Linux commands unless I explicitly say I'm on Mac.
- I am **learning terminal/command-line work**. When something can be done from
  the terminal, show me the terminal way and explain what each command does.

**How I want to be taught:**
- Do NOT just generate a finished repo and hand it to me. I will end up with a
  working bot and zero understanding.
- Work in **small steps**. One step at a time. Tell me exactly what to do,
  where to do it, and why it works. Then wait for me to run it and report back.
- Explain the **theory behind each piece** after I've seen it work — not before.
- Tell me when something I believe is wrong, and give me the better alternative.
  I prefer "no, but try this instead" over encouragement.
- Assume I know **Python basics only**. I do not know: virtualenv internals,
  HTTP/REST conventions, cron syntax, GitHub Actions, environment variables,
  or how feeds work beyond what's documented below.

**My constraints:**
- **Zero budget.** No paid APIs. No paid hosting. Free tiers only.
- Limited time. Prefer the simple solution that works over the elegant one.

---

## 1. WHAT THIS IS

A scheduled script that runs every morning, pulls new articles from a few
tech/AI sources, and sends me one Telegram message with title + source +
short summary + clickable link for each.

**Important framing I already learned:** this is NOT an agent. It is a
deterministic pipeline (cron job + API calls). An agent is an LLM in a loop
with tools, where the *model* chooses what to do next. This project is
deliberately built as a pipeline first; an agent rebuild is a later exercise.

---

## 2. CURRENT STATE — what already works

Built and verified by hand in the working session:

- Project folder `news-digest` with a virtualenv at `.venv`
- `feedparser` and `requests` installed
- `check_feeds.py` — probes candidate feeds, prints entry count, title, link,
  date, and description length
- Telegram bot created via @BotFather: **@NewsForKeshavBot**
- Bot token and chat_id obtained and tested — test message delivered, HTTP 200
- `digest.py` — fetches 3 feeds, filters last 24h, caps 3 per source, sorts
  newest-first, sends an HTML-formatted Telegram message. **Working.**

**Update 2026-10-18: Steps A–E are done and live.** Runs daily on GitHub
Actions (github.com/MKeshav04/news-digest); first cloud run succeeded.
See README.md for how everything works. Remaining: Steps F and G.

---

## 3. SOURCES — decided, with real measured data

| Source | Feed URL | Type | Description field |
|---|---|---|---|
| Lobsters | `https://lobste.rs/rss` | Aggregator | **Useless** — 94 chars of `<p><a>Comments</a></p>` |
| Simon Willison | `https://simonwillison.net/atom/everything/` | Publisher (Atom) | ~1600 chars, full post — must truncate |
| TechCrunch AI | `https://techcrunch.com/category/artificial-intelligence/feed/` | Publisher | ~210 chars, ideal as-is |

**Scope:** tech news and AI news only. Nothing else.

**Dropped:** DevURLs (no RSS feed — it's an "upcoming feature"; also redundant,
it aggregates HN + Lobsters; its HN column was 2 weeks stale).
Hacker News (too noisy, 30 links/day of everything).
Ars Technica main feed (firehose — carries science/health/cars, off-scope).

**Possible later additions:** arXiv `cs.AI` / `cs.CL` (abstract is in the feed,
zero fetching needed), a narrower Ars Technica category feed, HN Algolia API
filtered to `points > 150`.

---

## 4. HARD-WON FACTS — do not re-learn these

These came from actually running code, not from guessing. Respect them.

1. **Aggregators have no summaries.** Lobsters/HN link to other people's
   articles and write nothing. Publishers write real descriptions. This single
   distinction decides whether an LLM stage is needed.

2. **Description length lies.** Lobsters = 94 chars, Ars Technica = 92 chars.
   Nearly identical length, completely different value (a hyperlink vs. a real
   sentence). Always inspect content, never judge by length.

3. **Descriptions contain raw HTML** — `<p>`, `<a href>`, `<blockquote cite>`.
   Must be stripped before sending to Telegram or the message looks broken.

4. **Date formats differ between feeds.**
   - Lobsters: `Fri, 16 Oct 2026 15:18:36 -0500` (RFC 822, US Central)
   - Simon Willison: `2026-10-16T22:06:37+00:00` (ISO 8601, UTC)
   **Never parse `.published` as text. Always use `.published_parsed`**, which
   feedparser has already normalized to a UTC time tuple.

5. **RSS fields are optional.** Always `entry.get("summary", "")`, never
   `entry.summary` — missing fields raise AttributeError and kill the run.

6. **feedparser fails silently.** A blocked or rate-limited feed returns an
   object with `entries == []` and no exception. This already bit me once:
   Lobsters got rate-limited mid-session, contributed zero items, and the
   digest looked perfectly fine while being 100% wrong.
   **Every fetch must check `feed.get("status")` and `len(feed.entries)` and
   log loudly on failure.**

7. **Set a User-Agent.** Lobsters blocks anonymous library requests. Use:
   `feedparser.USER_AGENT = "KeshavNewsDigest/1.0 (+https://mishrakeshav.in)"`

8. **List order is not sort order.** A bug I hit: items were appended
   feed-by-feed, then sliced `[:8]`, so Lobsters filled every slot and the
   other two sources never appeared. Always sort explicitly and enforce a
   per-source cap.

9. **Telegram message limit is 4096 characters.** Roughly 10–12 items with
   summaries, or 30+ as bare titles.

---

## 5. ARCHITECTURE

```
TRIGGER (GitHub Actions cron, 01:30 UTC = 07:00 IST)
   |
SOURCES    feedparser over 3 feeds  -> check status, log failures loudly
   |
FILTER     published_parsed within last 24h
   |
DEDUPE     drop anything whose link is already in seen.json
   |
TRANSFORM  strip HTML, truncate summaries, blank Lobsters summaries
   |
SELECT     sort newest-first, cap per source
   |
FORMAT     two-tier Telegram HTML message (see section 6)
   |
DELIVER    POST api.telegram.org/bot<TOKEN>/sendMessage
   |
PERSIST    append sent links to seen.json
```

---

## 6. REMAINING WORK — build in this order

### Step A — Robustness (do first, it's small)
- Add `feedparser.USER_AGENT` line
- Add status + empty-entries check with a loud WARNING per feed
- Wrap the whole run in try/except; on exception, send me a Telegram message
  with the error. A digest bot that died silently three weeks ago is worse
  than no bot.

### Step B — Two-tier message
Replace the flat list with:
- **Top ~8 items**: title (hyperlinked), source, truncated summary
- **"Also today" block**: everything else as bare clickable titles, one line
  each, no summaries

Rationale: nothing is discarded, but only the top items compete for attention.
Rejected alternative: two messages per day — same content, double the
interruption, and I'd ignore the second one.

### Step C — Persistence (seen.json)
A scheduled job has no memory between runs. Without state it will re-send the
same articles whenever a feed republishes or runs overlap.

- `seen.json` holds a list of article URLs already sent
- On start: load it (handle the file not existing yet)
- Before formatting: drop any item whose link is in the set
- After a successful send: add the new links and write the file
- Cap it (keep the most recent ~500 URLs) so it doesn't grow forever
- **Only write after a successful send** — otherwise a failed send marks
  articles as seen and they're lost forever

### Step D — Secrets via .env
Token and chat_id are currently hardcoded. Move them out before touching Git.
- Use `python-dotenv`, load `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- `.env.example` is committed (placeholders only), `.env` is gitignored
- Explain to me what environment variables are and why this is the standard
  pattern — I don't know this yet.

### Step E — GitHub Actions
- Public repo (free unlimited Actions minutes)
- Secrets stored as repo secrets, injected as env vars
- `schedule: cron` at `30 1 * * *` (UTC) = 07:00 IST
- Also add `workflow_dispatch` so I can trigger manually — waiting 24h to
  debug is misery
- **Gotchas:** cron is UTC not IST; scheduled runs can be delayed 15+ min
  under load; GitHub auto-disables scheduled workflows after ~60 days of repo
  inactivity; `seen.json` must be committed back to the repo each run to
  persist (Actions runners are ephemeral)

### Step F — LLM summaries (later, optional)
Only needed to fill the Lobsters gap (aggregator = no summary). Would require
fetching the linked article (`trafilatura` for text extraction — expect ~30%
failures from paywalls, JS-only pages, PDFs, YouTube links) then summarizing.
Free options: Groq free tier (I already have a key), or Google AI Studio /
Gemini free tier. Build the failure fallback (summarize from title alone)
on day one, not after it crashes at 7 AM.

### Step G — Agent rebuild (the actual learning goal)
Rebuild the same job as a real agent: an LLM in a loop with tools
(`fetch_feed`, `fetch_article`, `send_telegram`), capped at ~10 iterations,
where the model decides what to do. Expect it to be slower, flakier and worse
than the pipeline. That's the point — the lesson is *when not to use an agent*.

---

## 7. FILES IN THE PROJECT

```
news-digest/
  .venv/              virtualenv (gitignored)
  .env                real secrets (gitignored, NEVER commit)
  .env.example        placeholder template (committed)
  .gitignore
  check_feeds.py      diagnostic probe for candidate feeds
  digest.py           the main script
  seen.json           sent-article state (to build)
  SPEC.md             this file
  .github/workflows/digest.yml   (to build)
```

---

## 8. USEFUL COMMANDS (Windows / PowerShell)

```powershell
# activate the virtualenv (needed in every new terminal)
.venv\Scripts\Activate.ps1

# run the bot
python digest.py

# quick feed probe without creating a file
python -c "import feedparser; f=feedparser.parse('https://lobste.rs/rss'); print(f.get('status'), len(f.entries), f.bozo)"
```

HTTP status meanings: 200 OK, 403 blocked, 429 rate-limited, 4xx my mistake,
5xx their server's problem.
