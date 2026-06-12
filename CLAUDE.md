# Facebook Rental Bot — Project Context

> This file is the full context for the project. Read it first in any new session.
> **Note about the user:** non-technical. Always explain in plain language with simple,
> numbered steps. Avoid jargon unless asked.

## What this bot does (in one paragraph)

It automatically hunts for apartment-rental posts on Facebook. Every 10 minutes it
opens a list of Facebook groups, reads the newest posts, and uses Claude (Haiku) to
judge each post against the user's rental criteria. When a post matches, it sends the
user a Telegram message with the details and a link. It remembers every post it has
already seen so the user never gets the same alert twice. It runs entirely in the
cloud on GitHub Actions — the user's computer does not need to be on.

## The user's rental criteria (high level)

Haifa — Naot Peres / Ramat HaNasi neighborhoods, 3+ rooms, 5000–6200 NIS/month,
balcony + elevator + shelter required. Exact criteria live in the `RENTAL_CRITERIA`
secret (and locally in `criteria.md`). Posts are in Hebrew; Claude handles any language.

## How it works (the pipeline)

1. **Scrape** (`scraper.py`) — Drives a real headless Chromium via **Playwright**,
   loading Facebook cookies into a real browser. Scrolls each group, extracts post
   text + post IDs/URLs. Returns up to 20 posts per group.
2. **Dedupe** (`db.py`) — Checks each post ID against `seen_posts.json`. New ones only.
3. **Analyze** (`analyzer.py`) — Sends each new post to Claude `claude-haiku-4-5` with a
   tool-call that returns `matches` (true/false), `reason`, and optional price/location/size.
4. **Notify** (`notifier.py`) — If it matches, sends a formatted Telegram message.
5. **Persist** — Marks the post seen in `seen_posts.json`.

`main.py` ties it together as a single-shot run: init → check active hours → run one cycle.

## Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point; one scrape→analyze→notify cycle. Active window 06:00–24:00 Israel time. |
| `scraper.py` | Playwright Facebook scraper. `SessionExpiredError` if cookies dead. |
| `analyzer.py` | Claude Haiku analysis via tool-calling. |
| `notifier.py` | Telegram alerts (and error alerts). |
| `db.py` | Dedupe state in `seen_posts.json`; error-alert cooldown in `error_state.json`. |
| `config.py` | Loads all settings from environment variables (falls back to local files). |
| `groups.txt` | Facebook group IDs to monitor (local; also the `GROUP_IDS` secret). |
| `criteria.md` | Rental criteria (local; also the `RENTAL_CRITERIA` secret). |
| `.github/workflows/check_rentals.yml` | The GitHub Actions schedule that runs it all. |

Note: `state.db` is an unused leftover from an old SQLite version — ignore it.
`cookies.json` is a Cookie-Editor *wrapper export*, NOT the format the scraper uses.

## Cloud deployment (GitHub Actions)

- **Repo:** https://github.com/tomasbrawe/Facebook_bot — **PUBLIC** (so Actions minutes
  are free/unlimited; the every-10-min cadence would exceed the private free tier).
  Default branch: `master`.
- **Schedule:** cron `*/10 3-21 * * *` (UTC) ≈ 06:00–24:00 Israel time.
- **State persistence:** each run commits the updated `seen_posts.json` back to the repo
  ("Update bot state [skip ci]"). This keeps dedup working AND keeps the repo active so
  GitHub doesn't disable the schedule after 60 days idle.
- **Secrets (6, in repo Settings → Secrets → Actions):**
  `ANTHROPIC_API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `FB_COOKIES`,
  `GROUP_IDS`, `RENTAL_CRITERIA`. Never printed/committed.

## Known gotchas (cost real debugging — don't relearn these)

1. **Facebook blocks plain HTTP scrapers** at the TLS/fingerprint level even with valid
   cookies. That's why we use a real browser via Playwright. Do not revert to `requests`.
2. **Telegram can't message a user until they message the bot first.** The bot is
   `@HaifaAppBot`; the user already did `/start`. Chat ID `425410499`.
3. **Setting the `FB_COOKIES` secret:** never source `.env` through bash — it strips the
   JSON quotes and corrupts the cookies. Pull the value with Python and pipe to stdin:
   `python -c "from dotenv import dotenv_values;import sys;sys.stdout.write(dotenv_values('.env')['FB_COOKIES'])" | gh secret set FB_COOKIES --repo tomasbrawe/Facebook_bot`
4. Pushing workflow files needs the `workflow` OAuth scope (`gh auth refresh -s workflow`),
   and git in a non-interactive shell needs `gh auth setup-git` for credentials.

## Most likely future problem: expired Facebook cookies

Cookies last weeks to months. When they die, the bot sends a Telegram alert
"Facebook session expired" and the scraper raises `SessionExpiredError`. Fix = export
fresh cookies and update the `FB_COOKIES` secret (using the Python-pipe method above).
This is almost always the cause of scraping failures — suspect it before the code.

## Common operator tasks

- **Check health / recent runs:** `gh run list --repo tomasbrawe/Facebook_bot`
- **See a run's log:** `gh run view <id> --repo tomasbrawe/Facebook_bot --log`
- **Run it now manually:** `gh workflow run check_rentals.yml --repo tomasbrawe/Facebook_bot`
- **Update a secret:** `gh secret set <NAME> --repo tomasbrawe/Facebook_bot` (pipe value via stdin)

A successful run with **0 matches is normal** — it just means none of the new posts fit
the criteria, so no alert was sent.
