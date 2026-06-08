# User Stories

**Stage 3 — Operationalize success as UX.** (Pair with `failure_modes.md` and `scenarios.md`.)

Turn the goal into concrete things a user wants to *do*. Each story is one sentence,
from the user's point of view. Keep them small and testable.

Format: **As a** _(who)_, **I want** _(to do something)_ **so that** _(benefit)_.

---

## Stories

### Onboarding
1. As a **new user**, I want to answer a few questions about my body and goals so that the bot calculates a realistic daily protein target for me.
2. As a **new user**, I want to override the suggested protein goal with my own number so that I can use a target I've already settled on.
3. As a **woman over 40**, I want to be asked about perimenopause during setup so that my protein goal accounts for the extra needs that come with hormonal changes.

### Logging food
4. As a **user**, I want to send a photo of my meal so that the bot estimates and logs the protein without me having to look anything up.
5. As a **user who cooks at home**, I want to describe my ingredients and get a per-portion estimate so that home-cooked meals are tracked as accurately as packaged food.
6. As a **user**, I want to save a home-cooked recipe so that I can log it again quickly next time without re-describing the ingredients.

### Tracking progress
7. As a **user**, I want to ask "how am I doing?" at any time so that I can see my running total and what I still need to eat.
8. As a **user**, I want a reminder at 15:00 so that I don't forget to hit my goal before the day is over.
9. As a **user outside CET**, I want to set my timezone so that the reminder arrives at 15:00 my local time, not some other time.

### Corrections
10. As a **user**, I want to correct a protein estimate after the fact so that my daily total stays accurate even when the bot guessed wrong.
11. As a **user who has logged several meals**, I want to pick which meal to correct so that I don't accidentally change the wrong entry.

### Suggestions
12. As a **user**, I want the bot to suggest what to eat for a specific meal so that I can hit my goal without having to think too hard about what to make.
13. As a **vegetarian or vegan user**, I want suggestions that match my diet so that I never get told to eat chicken.

---

## What "good" feels like

You send a photo, get a number back in seconds, and always know where you stand. It
feels like a knowledgeable friend who remembers what you ate — not a form to fill in.
The magic moment is the first time the 15:00 reminder arrives and already knows you're
behind; it makes the bot feel like it's actually paying attention.

---

## Out of scope (for now)

- Responding in the user's language (bot responds in English; understands all languages)
- Tracking macros other than protein (calories, carbs, fat)
- Suggesting a full day's meal plan proactively (suggestions are on-demand or at 15:00)
- Integration with external fitness apps or wearables
- Weekly summaries or progress charts
