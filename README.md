# News Digest Bot

A small Python bot that sends a daily tech/AI news digest to Telegram.
It runs for free on GitHub Actions every morning at 07:00 IST.

## What it does

- Reads RSS/Atom feeds from [Lobsters](https://lobste.rs),
  [Simon Willison](https://simonwillison.net) and
  [TechCrunch AI](https://techcrunch.com/category/artificial-intelligence/)
- Keeps stories from the last 24 hours and skips anything already sent
- Sends one Telegram message: the top 8 stories with summaries, then an
  "Also today" list of the rest as links
- Reports failing feeds in the message, and sends a crash alert if the run fails

## Setup

```powershell
git clone https://github.com/MKeshav04/news-digest.git
cd news-digest
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then fill in your values
python digest.py
```

You'll need a Telegram bot token from [@BotFather](https://t.me/BotFather)
and your chat id (see the comments in `.env.example`).

## Configuration

Set in `.env` locally, or as environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Bot token (required) |
| `TELEGRAM_CHAT_ID` | — | Chat to send to (required) |
| `LOOKBACK_HOURS` | 24 | How far back to look for stories |
| `MAX_SUMMARY_ITEMS` | 8 | Stories shown with summaries |
| `MAX_PER_SOURCE` | 3 | Max top stories from one source |

## Running on GitHub Actions

The workflow in `.github/workflows/digest.yml` runs daily at 01:30 UTC and can
be started manually from the Actions tab. Add `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` under **Settings → Secrets and variables → Actions**.
After each run the workflow commits `seen.json`, which records sent links so
stories aren't repeated.

## Files

- `digest.py` — the bot
- `check_feeds.py` — inspect a feed before adding it
- `seen.json` — links already sent
- `SPEC.md` — design notes and roadmap
