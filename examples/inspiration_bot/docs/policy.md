# Policy

> **Worked example** for the Inspiration Bot. (Stage 4: target behavior, step by step.)
> Most of this becomes system prompts + control flow.

## Tone

Warm, brief, a little playful — like a friend with a good eye, not a corporate assistant. One or
two sentences per reply. Name the *theme* it filed something under, so the user feels understood.
Never gushing, never robotic.

## On `/start` (first contact or repeat)

1. Upsert the user into `inspo_users` (keyed by `telegram_id`; capture `username`, `first_name`).
2. Reply with a short hello: what the bot does (you feed it photos & thoughts; it learns your taste
   and sends a morning nudge), and the two things to try first (send a photo; send a quote).
3. If an allowlist is configured and they're not on it: a polite "this bot isn't enabled for you,"
   and stop — store nothing.

## On an incoming photo or text (the reactive loop)

1. **Reject** unsupported types (voice, video, sticker, document) with a friendly one-liner.
2. **Understand** the item:
   - Photo → download it, describe it with a vision-capable model (what's in it, mood, aesthetic).
   - Text → take it as-is (a quote, thought, or link).
3. **Categorize** into 1–3 short themes (structured output).
4. **Store**: the image to R2 (UUID key) if a photo; a row in `inspo_items` (kind, content/description,
   image key, themes), scoped to the user.
5. **Update the profile**: feed *current profile + this new item* to the model and ask for a concise
   rewritten profile (a few sentences capturing recurring themes/aesthetics). Bounded, not appended —
   it can't grow forever. Save it on the user row.
6. **Confirm** in chat, naming the theme: "✓ filed — *quiet, foggy minimalism*."

## On `/inspire` and the morning job (the proactive loop) — the tool-using agent

A single **generator agent** produces one personal nudge. It has tools (all auto-scoped to *this*
user — see `architecture.md` on dependency injection) and decides what it needs:

- `recent_items(limit)` — what they've logged lately.
- `search_items(theme)` — past items on a theme it wants to build on.
- `recent_sends(limit)` — **what we've already sent, so it doesn't repeat itself.**
- `web_search(query)` — Perplexity (via OpenRouter) for something fresh and real, with sources.
- `check_schedule()` / `set_schedule(...)` — read and change *this user's* send preferences (see below).

The system prompt gives it the user's profile and today's date, and asks for: a short, personal
message (a reflection, prompt, or discovery), and a flag for whether a generated image would add to
it. If yes, orchestration generates one image (fal) — a deliberate, cost-aware step, not something
the model triggers freely. We then **record the send** in `inspo_sends` (so next time `recent_sends`
can keep it from repeating) and deliver it.

## On a scheduling request ("send me at 7am", "weekdays only", "pause", "when do you ping me?")

The agent handles this in chat via its `check_schedule` / `set_schedule` tools — there is **no
settings screen**. "Editing its schedule" means writing *this user's preferences* in the database
(`send_hour`, `timezone`, `cadence` of daily/weekdays/weekly, `paused`); the cron tick then honours
them (see `architecture.md`). It does **not** mean reconfiguring infrastructure — the agent never
touches Railway Cron itself.

- If the user gives a time but no timezone we don't know, **ask** ("what city/timezone are you in?")
  rather than guess — a 7am that fires at the wrong 7am is worse than asking once.
- After changing it, confirm in plain words: "Got it — I'll nudge you weekdays around 7am your time."
- "Pause" / "stop for a while" sets `paused = true`; "resume" clears it. Honest and reversible.

## Tool-permission principle (worth teaching)

- **Read tools** (the four lookups) — give freely; they're cheap and scoped.
- **Write tools** (`set_schedule`) — fine for the model when the change is **low-risk and reversible**.
- **Destructive or metered actions** stay out of the model's hands: deleting data is the
  human-confirmed `/delete` command, and generating an image is orchestrated by `jobs.py`, not a tool
  the model can spam. The model proposes; expensive/irreversible things require code or a human.

## On `/profile`

Show the stored profile in prose + the item count. Plain, honest, "here's what I think of you."

## On `/delete` (destructive — always confirm)

1. Reply with an inline keyboard: **[Yes, delete everything] [Cancel]**.
2. On **Yes**: delete the user's R2 images, their `inspo_items`, their `inspo_sends`, and the
   `inspo_users` row — in that order — then confirm "I've forgotten everything."
3. On **Cancel** or no response: change nothing.

## Always

- Scope every query by `telegram_id`. A user can only ever touch their own data.
- Keep one user's failure local — never crash the bot or abort the morning broadcast for others.
- Prefer cheap model tiers while iterating; the morning image is the one clearly metered cost.
