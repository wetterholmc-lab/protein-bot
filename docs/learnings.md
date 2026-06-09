# Learnings

**Stage 6 — Test atomic modules in isolation. Iterate. Keep learnings.**

As you build and test each module on its own, write down what you discover: which
prompt phrasing worked, which model/tier was good enough, surprising failures, costs,
quirks of a service. This saves you (and Claude) from re-learning the same things.

`journal.md` is the *chronological* trace; this file is the *distilled* "here's what we
know now" — keep it tidy and current.

---

## LLM / prompts

- **"fast" tier is enough for suggestion_engine and intent_classifier.** These need
  common sense and short output, not depth. Saving the "balanced" tier for food_analyzer
  where nuance matters (identifying mixed dishes, estimating reasonable ranges).
- **System prompt clarity on language beats language detection.** Adding "messages may
  be in any language" with 2–3 examples (French, German) was sufficient to make intent
  classification work multilingually — no separate detection step needed.
- **"Write the description in English" in ingredient_calculator** ensures meal descriptions
  stored in the DB are always in a consistent language, regardless of what the user types.
- **Protein ranges beat single numbers** — explicitly telling the model to return min/max
  (never a single value) gives more honest output and matches the hard rule.

## Models & tiers

- `fast` tier → intent_classifier, suggestion_engine, ingredient_calculator (quick, low-stakes)
- `balanced` tier → food_analyzer (needs image understanding + nuanced estimates)
- Vision model needed for food photos — food_analyzer uses a vision-capable model

## Telegram / python-telegram-bot

- **Only one bot instance can poll at a time.** Running `uv run proteinbot` twice causes
  a `telegram.error.Conflict` crash. Always `pkill -f proteinbot` before starting a new
  local instance. On Railway, duplicate deployed services with the same token cause the
  same error — delete duplicates immediately.
- **`drop_pending_updates=True` in `run_polling()`** clears stale updates from before the
  bot last ran. Important for clean restarts — prevents the bot from processing a backlog
  of old messages on startup.
- **Inline keyboard button labels must be short on mobile.** A single row of 4 buttons
  gives each button ~25% of screen width — labels get cut to one word. Use a 2×2 grid
  (`InlineKeyboardMarkup` with multiple rows) and keep labels to 1–2 words. Put context
  in the message text above the buttons instead.
- **`run_repeating` beats `run_daily`** for timezone-aware reminders. Hourly fire + local
  time check per user is simpler than calculating offsets upfront.

## Storage / DB

- **Add `timezone_offset` and `last_reminded_date` to the users table for timezone-aware
  reminders.** `last_reminded_date` prevents double-sends when the bot restarts mid-hour.
- **Prefix all table names with the project name** (`proteinbot_`) to avoid collisions on
  the shared Neon DB.
- **Never edit an applied migration** — add a new numbered file instead.
- **When adding an access gate to an existing system, add a defensive fallback in the auth check.**
  Migration backfills (`INSERT ... SELECT ... ON CONFLICT DO NOTHING`) can be skipped due to
  deployment timing or env var sequencing. Having `_is_authorized` also check `proteinbot_users`
  — "anyone with a completed profile is authorized" — prevents existing users from being locked
  out. Auto-backfill them into the auth table on the next interaction so future checks are instant.

## Railway deployment

- **`railway init` can time out silently** while still creating an empty project in the
  dashboard. If it hangs: cancel, check the dashboard for stale projects, delete them,
  then create the service via dashboard (Add → Empty Service) and use `railway link`.
- **One Telegram token = one running service.** If two Railway services share the same
  `TELEGRAM_BOT_TOKEN`, both will try to poll and crash each other in a conflict loop.
  Check all projects for duplicate tokens before debugging further.
- **Railway crash-restart loops are hard to break without a pause.** If a bot crashes
  immediately on startup, Railway restarts it before the old container fully shuts down,
  causing another conflict, causing another crash. Break the loop by redeploying from the
  dashboard, or waiting for all duplicate services to be removed.
- **Don't put `$PORT` in `startCommand`.** Railway runs without a shell; env vars don't
  expand. A polling bot has no inbound HTTP, so `$PORT` is irrelevant anyway.
- **Secrets via `railway variables --set` only** — `.env` is gitignored and dockerignored.

## Open questions

- How should the bot handle a user who hasn't set their timezone but is clearly not in CET?
  (Currently defaults to UTC+1; could ask during onboarding in a future version.)
