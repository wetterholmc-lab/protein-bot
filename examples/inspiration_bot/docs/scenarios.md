# Scenarios

> **Worked example** for the Inspiration Bot. (Stage 3: concrete walkthroughs = the stage-8 test checklist.)

## Happy path — reactive (you feed it)

1. New user opens the bot and taps **Start** (`/start`).
   **Expected:** a warm hello explaining what it does; a row is created in `inspo_users` keyed by
   their `telegram_id`; no "who are you?" friction.
2. They forward a **photo** of a misty pier.
   **Expected:** within a few seconds, "✓ filed — *quiet, foggy minimalism*"; the image is in R2,
   an `inspo_items` row exists, and their profile has nudged toward that aesthetic.
3. They send **text**: `"the best way to predict the future is to invent it"`.
   **Expected:** "✓ filed — *agency / making things*"; logged and folded into the profile.
4. They send `/profile`.
   **Expected:** a short prose read of their taste so far + item count — recognizably *them*.

## Happy path — proactive (it reaches out)

5. **Hourly cron tick fires** (`POST /cron/tick` in prod; `uv run inspo-cron` in dev).
   **Expected:** only users whose local hour + cadence are *due now* (and not already sent today) get
   **one** short, personal message built from their profile — e.g. a reflection or prompt, optionally
   with a generated image. Sends are per-user isolated; a re-fired tick double-sends no one.
6. A user impatient for more sends `/inspire`.
   **Expected:** the same kind of personal nudge, on demand, right now.

## Schedule, by chat

- User: *"actually ping me at 7am on weekdays"* → if timezone unknown, the bot asks for their city;
  then `set_schedule(hour=7, timezone="Europe/Berlin", cadence="weekdays")` and confirms in words.
- User: *"pause for a bit"* → `paused = true`; ticks skip them until they say *"resume."*
- User: *"when do you message me?"* → `check_schedule()` → "weekdays around 7am, Europe/Berlin."

## Delete / reset

7. User sends `/delete`.
   **Expected:** the bot asks to confirm with **[Yes, delete everything] [Cancel]**. On **Yes**:
   items, their R2 images, and the user row are gone; "Done — I've forgotten everything." On
   **Cancel** (or ignore): nothing changes.

## Edge & failure cases

- **Voice memo / sticker / video** → "I can take photos and text for now," nothing stored.
- **Photo that fails to download or describe** → "couldn't read that image — try again?"; bot stays up.
- **A user sends 20 things in a minute** → each filed independently; a failure on one doesn't block the rest.
- **`/cron/tick` called without the secret token** → `401`, nothing sent.
- **One user's profile errors during the morning job** → that user is skipped and logged; everyone else still gets theirs.
- **Same token in two places** → Telegram `409 Conflict`; the fix is the dev/prod token split (this is the lesson, see `architecture.md`).
- **Unknown user when an allowlist is set** → polite "this bot isn't enabled for you," no data stored.
