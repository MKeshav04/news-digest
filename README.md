# News Digest Bot

Every morning at **07:00 IST** a free GitHub computer wakes up, reads three
tech/AI news feeds, and sends one Telegram message to **@NewsForKeshavBot**
with the new stories. Your laptop doesn't need to be on.

This README explains everything, from zero.

---

## 1. The big picture

```
 07:00 IST — GitHub's clock (cron) fires
        │
        ▼
 A fresh Linux computer starts (GitHub Actions)
        │  downloads this repo, installs Python + requirements.txt
        ▼
 python digest.py
        │  1. read seen.json          ← "what did I already send?"
        │  2. fetch 3 RSS feeds       ← Lobsters, Simon Willison, TechCrunch AI
        │  3. keep last 24h only
        │  4. drop already-sent links
        │  5. build the message       ← top 8 with summaries + "Also today"
        │  6. send to Telegram        ← HTTP POST to api.telegram.org
        │  7. update seen.json
        ▼
 The workflow commits seen.json back to the repo
        │
        ▼
 The computer is deleted. Tomorrow, repeat.
```

This is a **pipeline**, not an agent: every step is fixed code, decided by
you in advance. Nothing "thinks". (An agent is when an LLM decides what to do
next — that's Step G in SPEC.md.)

---

## 2. Every file, and why it exists

| File | What it is | Committed to GitHub? |
|---|---|---|
| `digest.py` | The bot. All the logic. | Yes |
| `seen.json` | The bot's memory: links already sent (newest 500). Updated by the bot every day. | Yes — **must** be, see §5 |
| `requirements.txt` | Shopping list of Python packages, exact versions. GitHub's fresh computer installs from it. | Yes |
| `.github/workflows/digest.yml` | Instructions for GitHub Actions: *when* to run and *what* to do. | Yes |
| `.env` | Your real secrets (bot token, chat id). Only on your laptop. | **NEVER** |
| `.env.example` | Same as `.env` but with fake values. Tells future-you (or anyone cloning the repo) which settings exist. | Yes |
| `.gitignore` | List of things Git must never upload: `.env`, `.venv/`, caches. | Yes |
| `check_feeds.py` | Diagnostic tool: probes a feed and shows what's in it. Use it before adding a new source. | Yes |
| `SPEC.md` | The original plan, hard-won facts, and remaining steps (F, G). | Yes |
| `.venv/` | Your laptop's private Python install with the packages. Rebuildable, so never uploaded. | No |
| `.git/` | Git's hidden database of every commit. Don't touch it. | (it *is* the repo) |

---

## 3. digest.py, walked through in order

Read the file alongside this.

**Setup (top of file)**
- `load_dotenv()` — reads `.env` and puts each line into the process's
  environment variables (see §4). On GitHub there's no `.env`, so it does nothing.
- `feedparser.USER_AGENT = ...` — introduces the bot to websites. Lobsters
  blocks anonymous scripts; with a name, it lets us in.
- `TOKEN = os.environ.get(...)` and friends — read settings from environment
  variables. `or 24` means "use 24 if the setting is missing or empty".
- `FEEDS` — the three sources. `NO_SUMMARY` — Lobsters writes no descriptions
  (it's an aggregator), so we don't show one.

**`load_seen()` / `save_seen()`** — read/write `seen.json`.
- File missing (first ever run) → start with an empty list.
- `dict.fromkeys(links)` removes duplicates but keeps order; `[-500:]` keeps
  only the newest 500 so the file can't grow forever.
- Writes to `seen.tmp` then `os.replace()` swaps it in **in one step** — if the
  process dies mid-write, the old file survives intact instead of a corrupt half-file.

**`strip_html()`** — feed descriptions contain raw HTML (`<p>`, `<a>`). This
removes tags, turns `&amp;` back into `&`, and squashes whitespace.

**`collect_entries()`** — fetch + filter.
- `feedparser.parse(url)` downloads and understands a feed.
- **The loud check:** feedparser never crashes on failure — a blocked feed just
  returns zero entries. So we check `status` (HTTP code: 200 OK, 403 blocked,
  429 too many requests) and entry count. Failures are printed **and** listed at
  the bottom of the Telegram message, so you see them.
- `published_parsed` — every feed writes dates differently; feedparser
  normalises them to UTC. Never parse the text date yourself.
- `entry.get("title", ...)` — RSS fields are optional; `.get()` gives a default
  instead of crashing.
- Returns **all** items sorted newest-first, plus the list of problems.

**`split_tiers()`** — picks the top tier: walk newest-first, take an item if the
top has room (8) **and** its source hasn't used its 3 slots. Everything else goes
to "Also today". The per-source cap stops chatty Lobsters from filling the whole top.

**`build_message()`** — Telegram-flavoured HTML.
- `html.escape()` turns `&` `<` `>` into `&amp;` `&lt;` `&gt;`. Without it, a
  headline like `AT&T <Beta>` makes Telegram reject the whole message.
- **4096-character limit:** Telegram refuses longer messages. We add "Also today"
  lines until ~4000 chars, then write "…and N more".

**`send()`** — one HTTP POST to `https://api.telegram.org/bot<TOKEN>/sendMessage`.
That URL *is* the Telegram Bot API: you send data to it, Telegram delivers the
message. Any answer other than 200 **raises an error** so failure can't go unnoticed.

**`main()`** — the order matters: load seen → fetch → drop seen → **send** →
**then** save seen. If sending fails, the error jumps out of `main()` before the
save line, so stories aren't marked as sent and will go out next time.

**`run()`** — the safety net around everything.
- Missing token → stop immediately with a clear message.
- Any crash → full error text sent to you on Telegram ("⚠️ Digest crashed"),
  then `raise` re-throws it so the script exits with code **1**. GitHub reads
  that number: 0 = green ✓, anything else = red ✗ + email to you.

**`if __name__ == "__main__":`** — "only run when started directly, not when
imported". This let us import the file and fake a crash to test the alert.

---

## 4. The concepts you didn't know before

**Virtualenv (`.venv`)** — a private copy of Python just for this project, so
its packages don't clash with other projects. `.venv\Scripts\Activate.ps1`
makes `python` in that terminal mean *this* copy. Or call it directly:
`.venv\Scripts\python.exe digest.py`.

**Environment variables** — named values the operating system hands to every
program it starts, outside the code. Python reads them with `os.environ`.
Why use them for secrets: the code stays identical and public everywhere; each
place that runs it supplies its own secrets.
- Laptop: `.env` file → `load_dotenv()` → environment variables
- GitHub: repo Secrets → `env:` block in the yml → environment variables

**Why the token must never be in code** — the repo is public. Anyone with the
token fully controls the bot. Bots scan GitHub for leaked tokens within minutes.
If it ever leaks: @BotFather → `/revoke` → put the new one in `.env` and in the
GitHub secret.

**Git** — a tool that saves snapshots ("commits") of your folder's history on
your laptop. **GitHub** — a website storing a copy of that history.
- `git add` = choose what goes in the next snapshot
- `git commit -m "msg"` = take the snapshot (local only)
- `git push` = upload your snapshots to GitHub
- `git pull` = download snapshots others made (here: the bot's daily seen.json)
- `origin` = nickname for the GitHub address; `main` = the branch name

**GitHub Actions** — GitHub lends you a free Linux computer to run commands,
described in `.github/workflows/digest.yml`. Free and unlimited for public repos.
Each run starts on a brand-new machine and is wiped afterwards.

**Cron** — a time format with 5 fields: `minute hour day month weekday`.
`30 1 * * *` = minute 30, hour 1, every day/month/weekday, **in UTC**.
01:30 UTC + 5:30 = 07:00 IST.

**RSS / Atom feeds** — a machine-readable list a website publishes of its
latest posts (title, link, date, description). Publishers write real
descriptions; aggregators like Lobsters just link elsewhere.

**State** — a program forgets everything when it exits. `seen.json` is how one
run leaves a note for the next. On GitHub the computer is deleted after each
run, so the note has to be committed back into the repo.

---

## 5. The workflow file, line by line

- `on: schedule: cron` — run daily at 07:00 IST (GitHub may start it 15+ min late when busy).
- `on: workflow_dispatch` — adds the **Run workflow** button for manual tests.
- `permissions: contents: write` — allows the job to push the seen.json commit.
- `concurrency` — never two runs at once (they'd both read the same seen.json and double-send).
- `timeout-minutes: 10` — kill a stuck run instead of burning minutes.
- Steps: get code → install Python 3.11 (same as your laptop) → install
  requirements → run `digest.py` with secrets as env vars → commit `seen.json`
  if it changed (`git diff --quiet ||` = "commit only if something changed").

---

## 6. Your daily life now

**You do nothing.** The message arrives around 07:00 IST. A commit by
`github-actions[bot]` appears in the repo — that's the bot saving its memory.

Habits:
- **Don't run `digest.py` on your laptop for real any more.** The cloud is the
  only place the bot runs; a laptop run makes the two seen.json copies disagree.
- **Before editing anything: `git pull`** (gets the bot's latest seen.json).
- **To test a change:** `git add -A` → `git commit -m "what changed"` →
  `git push` → GitHub → Actions → Daily digest → **Run workflow**.

---

## 7. When something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| "⚠️ Digest crashed" in Telegram | Python error during the run | Actions tab → red run → click the red step → read the error |
| "⚠️ Feed problems" at the bottom | One feed was blocked/down; the rest still came through | Usually temporary. If it repeats for days, check the feed with `check_feeds.py` |
| "No new stories" | Nothing new in 24h (quiet day) — also proof the bot is alive | Nothing |
| **No message at all** | The bot itself didn't run or couldn't reach Telegram | Actions tab: is there a run? Red? Read its log |
| Email: "scheduled workflow disabled" | GitHub pauses schedules after ~60 days of repo inactivity | Actions → Daily digest → **Enable workflow** |
| `git push` rejected | GitHub has commits you don't (the bot's) | `git pull`, then push again |
| Token leaked | Anyone can control the bot | @BotFather `/revoke`, update `.env` + GitHub secret |

---

## 8. Useful commands (PowerShell, inside the `news-digest` folder)

```powershell
git pull                                  # get the bot's latest commits
git status                                # what changed locally?
git log --oneline -10                     # last 10 snapshots
.venv\Scripts\python.exe check_feeds.py   # probe the feeds
```

---

## 9. What's next (optional, see SPEC.md)

- **Step F** — LLM summaries for Lobsters links (free Groq/Gemini tier).
- **Step G** — rebuild as a real agent, to learn *when not to* use an agent.
