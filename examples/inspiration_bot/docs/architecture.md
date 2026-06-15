# Architecture

> **Worked example** for the Inspiration Bot. (Stage 5: atomic modules.) This is the example that
> introduces **environments**, **a tool-using agent**, **deployment via webhook**, and **cron**.

## The big idea: same code, two environments

The code is environment-agnostic; only *config values* differ. An `ENVIRONMENT` setting
(`development` | `production`, added to `agent/config.py`) decides behavior.

| | **development** (`.env`, your laptop) | **production** (Railway variables) |
|---|---|---|
| Bot token | `@yourname_dev_bot` | `@yourname_bot` |
| Database | a dev Neon DB / branch | the prod Neon DB |
| Updates | **long polling** (`inspo-bot`) | **webhook** into FastAPI (`inspo-serve`) |
| Scheduled send | `inspo-cron` run by hand | Railway Cron (hourly) → `POST /cron/tick` |

**Why separate bot tokens is mandatory, not optional:** Telegram allows exactly one update-consumer
per token. A second `getUpdates`, or a webhook *plus* a poller, returns `409 Conflict — terminated
by other getUpdates request`. So dev-polling and prod-webhook **must** use different tokens. That
hard constraint is what makes "environments" concrete: separate tokens, and separate databases so
test data and a careless dev migration can never touch real users.

## Modules (each does one thing)

| Module | Responsibility |
|---|---|
| `migrations/001_init.sql` | `inspo_users`, `inspo_items`, `inspo_sends` (project-prefixed tables) |
| `store.py` | all DB access, **every function scoped by `telegram_id`** (wraps `agent.services.db`) |
| `ingest.py` | one incoming item → understand (vision for photos) → categorize → store → update profile |
| `agent.py` | the pydantic-ai **generator agent**: its `Deps`, tools, and system prompt |
| `jobs.py` | `generate_for_user()` and `run_due_sends()` (loops due users, isolates failures) |
| `bot.py` | python-telegram-bot `Application`: command + message handlers, `build_application()` |
| `app.py` | FastAPI for prod: lifespan sets the webhook; `POST /telegram/<token>`; `POST /cron/tick` |
| entrypoints | `inspo-bot` (polling), `inspo-cron` (run due sends once), `inspo-serve` (webhook + cron HTTP) |

## The agent's tools — and why scoping is safe

The generator agent (`agent.py`) uses pydantic-ai's dependency injection: a `Deps` dataclass carries
the current `telegram_id`, passed via `deps=` at run time. Tools read `ctx.deps.telegram_id` — so
**the user id is injected, never a tool argument the model can choose.** The model literally cannot
ask for another user's data; scoping isn't a prompt instruction it might ignore, it's structural.

| Tool | Backed by | Purpose |
|---|---|---|
| `recent_items(limit)` | `store.recent_items` | what this user logged recently |
| `search_items(theme)` | `store.search_items` | past items on a theme to build on |
| `recent_sends(limit)` | `store.recent_sends` | **anti-repetition** — what we already sent |
| `web_search(query)` | `llm.research()` (Perplexity/Sonar) | fresh, real-world material + sources |
| `check_schedule()` | `store.get_user` | read this user's send prefs |
| `set_schedule(hour, timezone, cadence, paused)` | `store.set_schedule` | change them — **low-risk, reversible write** |

`set_schedule` is the one tool that *writes*. That's deliberate: read tools are free to grant, a
reversible write is fine for the model, but destructive (`/delete`) and metered (image generation)
actions stay in human-confirmed code — see `policy.md`'s tool-permission principle.

Today's date and the user's profile go in the **system prompt** (not tools) — the model needs them
every time and shouldn't have to ask. Image generation is an **orchestrated** step (the agent returns
a "wants image" flag; `jobs.py` calls `media` if so), keeping a metered cost out of the model's hands.

## Data model

```
inspo_users(telegram_id PK, username, first_name, profile TEXT DEFAULT '',
            send_hour INT DEFAULT 8, timezone TEXT DEFAULT 'UTC',     -- schedule prefs
            cadence TEXT DEFAULT 'daily',  -- 'daily' | 'weekdays' | 'weekly'
            paused BOOL DEFAULT false, created_at, last_sent_at)
inspo_items(id PK, telegram_id, kind 'photo'|'text', content TEXT,
            image_key TEXT NULL, themes TEXT[], created_at)         -- index (telegram_id)
inspo_sends(id PK, telegram_id, body TEXT, image_key TEXT NULL, created_at) -- index (telegram_id)
```

## Data flow

```
REACTIVE (you → bot):
  photo/text → bot.py handler → ingest.py
        ↳ photo: download → vision model (image→text)
        ↳ categorize (themes) → store.add_item (+ R2 image)
        ↳ store.update_profile(current + new → rewrite)
        ↳ reply "✓ filed — <theme>"

PROACTIVE (bot → you):  /inspire (one user, now)   or   cron tick (the due ones)
  trigger → jobs.generate_for_user(telegram_id)
        ↳ agent.run(deps=Deps(telegram_id), profile, today)
              ↳ tools: recent_items / search_items / recent_sends / web_search
        ↳ optional media.text_to_image (if agent asked)
        ↳ store.record_send → bot sends message (+image)
```

## Scheduling: one tick, a per-user due-check

Because each user picks their own hour/timezone/cadence, we don't schedule per user on Railway.
Instead **Railway Cron calls `POST /cron/tick` once an hour**, and `jobs.run_due_sends()` decides who's
due: for each non-paused user, compute their *local* time from `timezone`; if the local hour matches
`send_hour`, their `cadence` allows today, and `last_sent_at` isn't already today, send and stamp
`last_sent_at`. That last check makes the tick **idempotent** — a retried or doubled tick can't
double-send. This "frequent tick + due-check in code" is the general pattern for per-user schedules
without a job queue. (`inspo-cron` runs the same `run_due_sends()` once, for local testing.)

## Services used (the starter toolbox)

- `llm` — `build_model()` for the vision/ingest + generator agents; `research()` as the `web_search` tool.
- `media` — `text_to_image(persist=True)` for the optional morning image (→ R2).
- `storage` — R2 for uploaded photos and generated images (UUID keys, `prefix="inspo"`).
- `db` — `apply_migrations()` on startup; all queries via `store.py`, parameterized, `telegram_id`-scoped.

## Deploy shape (Railway)

- One **web service** runs `inspo-serve` (FastAPI). On startup it registers the webhook with the prod
  token; `fastapi run` reads `PORT` itself (don't put `$PORT` in the start command).
- `POST /telegram/<token>` receives updates; the secret path/token rejects forgeries.
- `POST /cron/tick` requires a secret token header; an **hourly Railway Cron** job calls it, and the
  due-check (above) decides who actually gets a send.
- All secrets are Railway variables, never the committed `.env`. (See repo `docs/deploy.md`.)
