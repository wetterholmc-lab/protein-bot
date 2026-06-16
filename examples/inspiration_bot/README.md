# Inspiration Bot — a Telegram agent (the "works both ways" demo)

A Telegram bot that learns what inspires you and nudges you with it. It shows an agent
that works in **both directions**:

- **Reactive** — you forward a photo or send a thought; it understands it (vision for
  photos), files it, and quietly evolves a profile of your taste.
- **Proactive** — on a schedule it reaches out *first* with one short, personal nudge,
  built from your profile and tools, never repeating itself.

It's the third worked example, and it's where the starter introduces four things the
other examples don't: **environments** (dev vs prod), a **tool-using agent**, **deployment
by webhook**, and **cron**. Read the design docs in [`docs/`](docs/) — they're the method
(problem → policy → architecture) filled in for this bot.

## What it teaches

- **Telegram is your auth.** No signup/login/passwords — every update carries a verified
  `telegram_id`. Your "users table" is just keyed on it. Authorization (who's *allowed*) is
  a separate, optional allowlist.
- **Environments.** The same code reads `TELEGRAM_BOT_TOKEN` / `DATABASE_URL` / `ENVIRONMENT`;
  only the *values* differ between your laptop (`.env`) and Railway. You **must** use a
  different bot token per environment (Telegram allows one update-consumer per token).
- **Tool-using agent with safe scoping.** The generator agent has read tools (what you
  saved, what we sent) + one reversible write tool (set your schedule). The user id is
  *injected* via dependency injection — never a tool argument the model can choose — so it
  physically cannot touch another user's data. Destructive (`/delete`) and metered (image
  generation) actions are kept out of the model's hands.
- **Cron via a tick + due-check**, and **webhook vs polling** chosen by environment.

## Prerequisites (`.env`)

| Variable | Needed? | What |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | **yes** | A **dev** bot token from [@BotFather](https://t.me/BotFather) (`/newbot`). Use a *separate* token for production. |
| `OPENROUTER_API_KEY` | **yes** | LLM + vision + Perplexity search. |
| `DATABASE_URL` | **yes** | Neon Postgres — stores users, items, sends. |
| `R2_*` | **yes** | Stores the photos you send and any generated images. |
| `FAL_KEY` | optional | Only for the morning *image*; without it, nudges are text-only. |
| `ALLOWED_TELEGRAM_IDS` | optional | Comma-separated user ids allowed to use the bot. Empty = open (fine for dev). |
| `ENVIRONMENT` | optional | `development` (default) or `production`. |

## Run it locally (long polling — no public URL needed)

```bash
# 1) Chat with your bot: open Telegram, find your bot, send /start, then a photo or a quote.
uv run python -m examples.inspiration_bot.bot

# 2) In another terminal, fire the proactive "morning" nudge right now (dev = ignores the clock):
uv run python -m examples.inspiration_bot.cron
```

Try: `/start`, send a photo, send a quote, `/profile`, `/inspire`, tell it *"send me at 7am
on weekdays"*, then `/delete`.

## Deploy it (Railway — webhook + cron)

In production the bot switches from polling to a **webhook** into a FastAPI app, and a
**Railway Cron** runs the nudge on a schedule. See the repo's [`docs/deploy.md`](../../docs/deploy.md)
for the full walkthrough. The short version:

1. **Make a second, production** bot with @BotFather (different token).
2. Deploy the web service with start command `fastapi run examples/inspiration_bot/app.py`
   (it reads `$PORT` itself — don't pass it).
3. Set Railway **variables** (not `.env`): `ENVIRONMENT=production`, the prod
   `TELEGRAM_BOT_TOKEN`, a prod `DATABASE_URL`, `R2_*`, `FAL_KEY`, plus
   `PUBLIC_URL=https://<your-app>.up.railway.app`, a random `TELEGRAM_WEBHOOK_SECRET`, and a
   random `CRON_SECRET`. On boot the app registers its webhook automatically.
4. **Schedule the nudge**, either:
   - a second Railway **Cron service** (same repo/vars) running
     `python -m examples.inspiration_bot.cron` hourly (`0 * * * *`) — it honours each user's
     schedule because `ENVIRONMENT=production`; or
   - any scheduler that does `POST $PUBLIC_URL/cron/tick` hourly with header
     `X-Cron-Secret: <CRON_SECRET>`.

## Files

```
bot.py      handlers + Application wiring; `python -m ... .bot` runs polling (dev)
app.py      FastAPI: the Telegram webhook + POST /cron/tick (prod; `fastapi run`)
cron.py     `python -m ... .cron` fires the proactive loop (dev: now / prod: due-only)
agent.py    the generator agent: Deps (injected scope), tools, system prompt
ingest.py   reactive loop: understand (vision/text) → store → evolve the profile
jobs.py     is_due() (pure, tested) + run_due_sends() (per-user, failure-isolated)
store.py    all DB access, every query scoped by telegram_id
migrations/ 001_init.sql — inspo_users / inspo_items / inspo_sends
```
