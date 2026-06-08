# Architecture

**Stage 5 — Break it into atomic modules.**

Decompose the agent into the smallest pieces you can build and **test in isolation**
(stage 6). Each piece should do one thing. Then you'll compose them (stage 7).

---

## The pieces

| Module | Does one thing | Input → Output |
|--------|----------------|----------------|
| `telegram_handler` | Receive messages from Telegram and route them | Telegram update → routed to the right module |
| `intent_classifier` | Decide what the user wants from a text message; handles input in any language | Text (any language) → intent (`status` / `correction` / `meal_suggestion` / `off_topic`) + extracted values |
| `food_analyzer` | Estimate protein in a food photo using a vision model | Image → food description + protein range (min/max g) |
| `ingredient_calculator` | Calculate protein per portion from a free-text ingredient list; handles any language | Ingredients + quantities + portions (any language) → protein per portion (min/max g) |
| `meal_logger` | Write a meal entry to the database | Meal data → saved row |
| `daily_tracker` | Sum today's logged meals and compare to the goal | user_id + date → total logged g, goal g, deficit g, meal list |
| `goal_calculator` | Calculate a personal protein goal from onboarding data | age, weight, height, sex, activity, goal, diet_style → goal in g/day |
| `suggestion_engine` | Generate food suggestions and contextual meal feedback | Three functions: post-meal feedback (time-aware), meal-type suggestions on request, 15:00 reminder suggestions |
| `correction_handler` | Apply a user correction to a logged meal; if 2+ meals today, shows a keyboard to select which one | meal_id + corrected_protein_g → updated row |
| `recipe_store` | Save and retrieve named recipes | ingredients + portions → saved recipe / recipe_id → recipe |
| `reminder_scheduler` | Trigger the 15:00 check-in for each user at their local time | hourly job → per user: compute local hour from `timezone_offset`, send only at 15:00 local, skip if already sent today |
| `onboarding` | Walk the user through setup questions and save their profile | Telegram conversation → saved user profile + calculated goal |

---

## Which starter services does each use?

- **`llm`** (vision + chat) — `food_analyzer` (vision model for photos), `intent_classifier`,
  `suggestion_engine`, `ingredient_calculator` (for ambiguous quantities)
- **`db`** (Neon/asyncpg) — `meal_logger`, `daily_tracker`, `recipe_store`,
  `correction_handler`, `onboarding`, `reminder_scheduler`
- **`storage` (R2)** — not needed; photos are analyzed in-flight, not stored
- **`media` (fal)** — not needed for this agent

External:
- **Telegram Bot API** — `telegram_handler`, `reminder_scheduler` (sending messages)

---

## Data flow

### Food photo
```
Telegram photo
  → telegram_handler
  → food_analyzer (vision LLM)
      → if clear food: meal_logger → daily_tracker → reply with estimate + total
      → if home-cooked: ask for ingredients → ingredient_calculator → meal_logger
                        → daily_tracker → reply + offer to save recipe
      → if unclear: reply asking for better photo or description
      → if not food: reply asking if wrong photo was sent
```

### Text message
```
Telegram text
  → telegram_handler
  → intent_classifier
      → status:          daily_tracker → reply with total, goal, deficit, meal list
      → correction:      correction_handler → daily_tracker → reply with updated total
      → meal_suggestion: daily_tracker → suggestion_engine → reply with meal ideas
      → onboarding:      onboarding → goal_calculator → save profile → reply with goal
      → off_topic:       reply redirecting to protein tracking
```

### 15:00 reminder (timezone-aware)
```
reminder_scheduler (run_repeating, every hour)
  → for each user: compute local hour from timezone_offset
  → skip if local hour ≠ 15, or already sent today (last_reminded_date)
  → daily_tracker
      → goal reached: send positive confirmation
      → deficit:      ask about dinner plans
                        → yes: suggestion_engine (dinner ideas + snack if needed) → reply
                        → no:  suggestion_engine (snack ideas) → reply
```

---

## Data you store

All table names are prefixed with `proteinbot_` to avoid collisions with other projects
on the shared Neon database.

### `proteinbot_users`
Stores the user profile set during onboarding.

| Column | Type | Notes |
|--------|------|-------|
| `telegram_id` | `bigint PRIMARY KEY` | Telegram user ID |
| `age` | `int` | |
| `weight_kg` | `float` | |
| `height_cm` | `float` | |
| `sex` | `text` | `female` / `male` / `other` |
| `activity_level` | `text` | `sedentary` / `moderate` / `regular` / `hard` |
| `goal` | `text` | `maintain` / `lose_weight` / `build_muscle` |
| `diet_style` | `text` | `omnivore` / `vegetarian` / `vegan` |
| `pregnant_or_breastfeeding` | `bool` | `null` if not asked |
| `perimenopausal` | `bool` | `null` unless female 40+ and not pregnant; +15g to goal if true |
| `protein_goal_g` | `int` | Calculated at onboarding; recalculated if profile changes |
| `timezone_offset` | `smallint` | Hours from UTC; default 1 (CET). Set via `/timezone` command. |
| `last_reminded_date` | `date` | Date the 15:00 reminder was last sent; prevents double-sends on restart. |
| `created_at` | `timestamptz` | |

### `proteinbot_meals`
One row per logged meal.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `serial PRIMARY KEY` | |
| `telegram_id` | `bigint` | FK → `proteinbot_users` |
| `logged_at` | `timestamptz` | When the meal was logged |
| `description` | `text` | What the agent understood (e.g. "grilled chicken + rice") |
| `protein_min_g` | `int` | Low end of the estimated range |
| `protein_max_g` | `int` | High end of the estimated range |
| `protein_actual_g` | `int` | Set if the user corrected the estimate; `null` otherwise |
| `recipe_id` | `int` | FK → `proteinbot_recipes` if from a saved recipe; `null` otherwise |

### `proteinbot_recipes`
Saved home-cooked recipes for reuse.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `serial PRIMARY KEY` | |
| `telegram_id` | `bigint` | FK → `proteinbot_users` |
| `name` | `text` | User-provided or inferred (e.g. "lentil soup") |
| `ingredients` | `jsonb` | List of `{ingredient, quantity_g}` |
| `portions` | `int` | How many portions the recipe makes |
| `protein_per_portion_min_g` | `int` | |
| `protein_per_portion_max_g` | `int` | |
| `created_at` | `timestamptz` | |
