# Journal

This is the running trace of your thinking as you build. It's the most important
document in the project — more than any single piece of code.

**How to use it**
- Add an entry at *meaningful* moments: a decision (and **why**), something you
  learned, a dead end you backed out of, a milestone reached.
- **Not** every edit. Capture the thinking, not the keystrokes.
- Always **timestamp** with date **and** time. Newest entries go at the bottom.
- Both you and Claude should add entries.

Format:

```
## YYYY-MM-DD HH:MM — Short title
What you were trying to do, what you decided, and why. What you learned.
```

---

## 2026-05-29 12:00 — Project initialized from the agent starter
Cloned the starter. Next: fill in `docs/problem.md` (what can't I do today?) and the
"Your project" section of `README.md` (what am I building?). Then design before coding.

## 2026-06-07 — Chose project and designed the foundation: protein-tracking Telegram bot

**The project:** A Telegram bot that helps Caroline track protein intake via food photos.

**The problem (stage 1):** Caroline needs to eat more protein due to age, but doesn't know
which foods are high in protein or whether she's gotten enough during the day. She wants
easy logging, daily feedback, and a timely nudge if she's falling behind.

**Decisions made:**

- **Interface:** Telegram bot. Photo → logged, no forms. Chosen because friction must be
  minimal — otherwise people don't log.

- **Protein goal:** The agent calculates a personal goal based on age, weight, height, and
  sex (not a fixed default). Rationale: an accurate goal requires personal data.

- **Reminder:** At 15:00 every day. If Caroline is under her goal → reminder with how much
  is missing. If she's already hit her goal → positive confirmation instead.

- **Learning from corrections:** If the agent guesses the wrong protein amount, Caroline can
  correct it ("no, it was 28g"). The correction is saved in the database and prioritized the
  next time the same food appears. The agent always confirms the correction before saving.

- **Estimates are always approximate:** The agent should never give confidently exact numbers.
  "About 25–35g" is the right format, not "31.4g".

**User stories done (6):** photo logging, daily status, 15:00 reminder, weekly summary,
ask about protein content, correct and learn.

**Failure modes identified:** unclear photo, mixed dish, wrong guess, forgotten logging,
non-food photo, goal already reached, network error, wrong correction.

**Protein goal — onboarding questions (beyond age, weight, height, sex):**
Activity level and goal are the most important variables (can shift the target by 50–100%).
Diet style affects bioavailability of plant proteins.
Pregnancy/breastfeeding question is only asked of users who specified sex = female.
Medical conditions (e.g. kidney disease) are not handled — the agent refers to a doctor.

Full onboarding sequence:
1. Age, weight, height, sex (female / male / other or prefer not to say)
2. Activity level (sedentary / moderately active / exercises regularly / trains hard)
3. Goal (maintain muscle / lose weight / build muscle)
4. Diet style (omnivore / vegetarian / vegan)
5. (Everyone except "male") Pregnant or breastfeeding? (yes / no)

Sex "other / prefer not to say" → protein goal calculated as average of female and male
formulas.

**The 15:00 reminder asks about dinner plans (option 1):**
If protein is missing, the agent asks "Are you planning dinner tonight?" before suggesting a
snack. Otherwise the user risks eating both a snack and dinner and overshooting the goal.
Option 2 (learns from history) can be added later once data exists.

**Ingredient calculation + recipe memory:**
For home-cooked food (stew, soup, etc.) the agent asks for ingredients, quantities, and
number of servings and calculates protein per portion. Saves the recipe if the user wants —
reused next time the same dish is logged. Tied to the correction-learning feature.

**Next step:** Scenarios (stage 3) — concrete walkthroughs with real example inputs.

## 2026-06-07 — Wrote scenarios, failure modes, and policy (stages 3–4)

**Scenarios** (`docs/scenarios.md`) — 8 concrete end-to-end walkthroughs:
- Happy paths: simple food photo, home-cooked food with ingredients, status check on demand,
  15:00 reminder with deficit, 15:00 reminder with goal already reached.
- Edge cases: blurry photo, non-food photo, wrong guess → correction and learning.

Key decisions in scenarios:
- Status is triggered by natural language ("status", "how am I doing?", "what's left?"),
  not only by an exact command — bot must understand intent.
- Every food-log reply always shows the running daily total, unprompted.
- 15:00 reminder asks about dinner plans before suggesting snacks to avoid overshooting.
- Correction is always confirmed before it is saved.

**Failure modes** (`docs/failure_modes.md`) — 13 failure cases documented:
- Each has likelihood, severity, and how the agent handles it gracefully.
- Hard rules: never a single precise protein number, never log from an unidentifiable photo,
  never save a correction without confirmation, never handle medical questions.
- User-facing error messages are always short, honest, and give a clear next step.

**Policy** (`docs/policy.md`) — 5 step-by-step flows:
onboarding, food photo, status request, correction, 15:00 reminder.
- Suggestion engine added to the 15:00 flow: concrete dinner ideas with protein estimates,
  snack only if the deficit is likely to remain after dinner.
- Tool table clarifies which service each module uses.
- Tone rules: concise, warm, never preachy, always approximate ranges.

## 2026-06-07 — Built the full codebase (stage 5–6 start)

**Architecture** (`docs/architecture.md`) — 12 atomic modules designed, three DB tables,
three data flow diagrams (photo, text, scheduler). Decided not to use R2 or fal.ai —
photos are analysed in-flight via vision LLM and don't need to be stored.

**Code built** (`src/agent/agents/proteinbot/`):

- `models.py` — Pydantic models + StrEnum for all domain types.
- `goal_calculator.py` — protein goal formula: base g/kg by activity, age bump at 40+/50+,
  goal multiplier, sex multiplier, +25g for pregnancy, +10g buffer for vegan diet.
- `food_analyzer.py` — pydantic-ai Agent with vision model (balanced tier = claude-sonnet),
  returns structured `FoodEstimate` with is_food, is_identifiable, is_home_cooked flags.
- `ingredient_calculator.py` — LLM parses free-text ingredient list + portions → protein
  per portion range. Uses "fast" tier since it's straightforward arithmetic.
- `intent_classifier.py` — classifies text as status / correction / off_topic; also
  extracts corrected gram value for corrections. Fast-tier LLM + heuristic shortcut.
- `suggestion_engine.py` — generates dinner or snack suggestions respecting diet style.
- `meal_logger.py`, `daily_tracker.py`, `correction_handler.py`, `recipe_store.py` —
  DB read/write modules, each doing exactly one thing.
- `bot.py` — Telegram bot wiring: ConversationHandler for onboarding (8 states),
  photo handler, text handler (state machine via user_data), dinner callback,
  daily 15:00 JobQueue reminder. Uses PTB v22 `post_init` hook for migrations.

**Key technical decisions:**
- `_ud(context)` helper asserts `context.user_data is not None` once, keeping all
  handlers clean without repeated guards.
- `run_polling()` is called synchronously from `main()` — PTB v20+ manages its own
  event loop; wrapping it in `asyncio.run()` caused a type error.
- Migrations run via PTB's `post_init` hook, not a separate `asyncio.run()` call,
  to avoid nested event loop issues.
- 15:00 reminder uses inline keyboard buttons (dinner_yes / dinner_no) rather than
  waiting for free text, so the dinner callback is unambiguous regardless of what the
  user types next.

**Status:** ruff clean, pyright 0 errors. Ready to wire up credentials and run live.

## 2026-06-07 — Added custom protein goal override

Users now get a suggested goal at the end of onboarding but can override it. The flow:
1. Agent calculates suggested goal and shows it with two buttons: "Use Xg" / "Set my own".
2. If "Set my own": bot asks for a number (validated 10–500g) and saves that instead.

Added two new ConversationHandler states: `OB_CONFIRM_GOAL` and `OB_CUSTOM_GOAL`.
The suggested goal is stored temporarily in `KEY_PROFILE_DRAFT["_profile_json"]` as a
serialised UserProfile so `ob_confirm_goal` can save it without recalculating.

Policy and scenarios updated to reflect this.

## 2026-06-07 — Added perimenopause/menopause question for women 40+

Oestrogen drop during peri/menopause accelerates muscle loss and raises protein needs.
Added +15g/day to the goal for users who answer yes.

Changes:
- `migrations/002_proteinbot_menopause.sql` — adds `perimenopausal bool` column.
- `models.py` — `perimenopausal: bool | None` added to `UserProfile`.
- `goal_calculator.py` — +15g if `perimenopausal` is True.
- `bot.py` — new state `OB_MENOPAUSE`; question triggers only for `sex == "female"` AND
  `age >= 40` AND `not pregnant`. Males and "other" skip it. Pregnant women skip it too
  (pregnancy and menopause are mutually exclusive in practice).

## 2026-06-07 — Added /reset command for testing

`/reset` deletes all meals, recipes, and the user profile from the database and clears
`context.user_data`. Makes it possible to re-run onboarding without touching the DB manually.
This is a dev/test tool — worth removing or gating before any public release.

## 2026-06-08 — Debugged two bugs found during live testing

**Bug 1: Menopause question not appearing.**
Added `logger.debug()` to `ob_pregnant` to log `pregnant`, `sex`, and `age` at runtime.
Root cause not yet confirmed from logs (user ran reset and restarted before logs were captured),
but the question works after the second bug was fixed.

**Bug 2: Bot looped back to "Type /start to set up your profile first" after typing age.**
Root cause: multiple bot instances were running simultaneously. Each previous call to
`uv run proteinbot` in the chat started a new background process without stopping the old one.
Conversation state is stored in memory per process — one instance handled `/start` and set
state to `OB_AGE`, a different instance received the age text and had no state for that user,
so it fell through to `handle_text` which returned the /start prompt.

Fix: `pkill -f proteinbot && uv run proteinbot` to kill all instances and start exactly one.
Lesson: always kill the old bot before starting a new one during local testing.

## 2026-06-08 — Added contextual meal feedback and on-demand meal suggestions

**Feature 1: Contextual feedback after every logged meal.**
After logging any meal (photo or home-cooked), the bot now comments on whether the
protein amount is appropriate for the time of day relative to the daily goal.

Implementation: `suggestion_engine.feedback_after_meal()` takes meal protein, daily total,
goal, diet style, and current hour. A time-based lookup table maps hours to expected
cumulative fractions of the daily goal (e.g. by 9am ~20% expected, by 1pm ~50%). The
distance between actual and expected determines the tone: on track, a bit low, or great
start. If low, 1–2 concrete food additions are suggested. Uses "fast" tier LLM.

**Feature 2: Meal suggestions on demand.**
The user can ask "what should I eat for lunch?" or "middag förslag?" and the bot responds
with 2–3 concrete suggestions calibrated to the remaining daily deficit.

Implementation: added `meal_suggestion` as a fourth intent in `intent_classifier`, with
`meal_type` extracted (e.g. "lunch", "dinner"). `suggestion_engine.suggest_for_meal()`
takes the meal name, remaining grams, and diet style. If the goal is already reached, the
bot says so and offers suggestions as inspiration only.

**Docs updated:** policy.md, scenarios.md, architecture.md, failure_modes.md all synced
to reflect the two new features, the perimenopause question, and the custom goal flow.
