# Failure Modes

**Stage 3 — Operationalize *failure* as UX.**

Agents fail in ways normal programs don't: they make things up, misread intent, call
the wrong tool, or cost money and time. Decide *now* how the agent should fail
**gracefully and honestly** instead of confidently-wrong.

---

## Failure table

| What could go wrong | How likely / how bad | How the agent should handle it |
|---------------------|----------------------|-------------------------------|
| Photo is blurry or ambiguous | High / mild | Ask for a better photo or text description. Never guess from a bad image. |
| Photo is not food | Medium / mild | Ask if the user meant to send a different photo. Log nothing. |
| Mixed or home-cooked dish — hard to estimate | High / mild | Ask for ingredients, quantities, and number of portions before estimating. |
| Agent's protein estimate is significantly wrong | Medium / bad | User can correct at any time. Correction confirmed before saving. Never argue — accept the correction. |
| User sends a correction that seems unrealistic (e.g. "500g protein") | Low / bad | Flag it: "That's quite high — are you sure? I want to make sure I log the right number." Confirm before saving. |
| User never responds to a follow-up question (ingredients, dinner plans, etc.) | Medium / mild | Don't re-ask. Leave the conversation open. Log nothing until the user responds or logs something new. |
| User forgets to log a meal | High / mild | The agent does not police this. It only works with what it's given. Estimates are explicitly approximate for this reason. |
| User asks about a medical condition (kidney disease, diabetes, etc.) | Low / bad | Do not attempt to advise. Reply: "That's outside what I can reliably help with — worth checking with your doctor." |
| User asks something completely off-topic | Medium / mild | Politely redirect: "I'm only set up to help with protein tracking — anything I can help you log?" |
| Vision model / LLM API is down or times out | Low / bad | Catch the error. Tell the user plainly: "I'm having trouble processing that right now — try again in a moment." Log the error internally. Never show a stack trace. |
| Database is unavailable | Low / bad | Tell the user the log couldn't be saved and ask them to try again. Do not silently drop data. |
| Telegram scheduler fails to send the 15:00 reminder | Low / mild | Log the failure. The user won't notice a missed reminder — don't send a double reminder later. |
| Onboarding data seems off (e.g. weight of 5kg) | Low / bad | Ask the user to confirm before saving: "Just checking — did you mean 50kg?" |
| User's goal is already reached at 15:00 | Expected / fine | Send a positive confirmation only. No snack suggestion, no reminder to eat more. |
| Contextual feedback after meal is off (e.g. wrong time of day assessment) | Medium / mild | Feedback is best-effort and time-based — the bot should never be judgmental. If the user disagrees, they can ignore it. |
| User asks for meal suggestions but has no profile yet | Low / mild | Redirect to /start to set up a profile first. |
| Meal suggestion intent is misclassified (e.g. "what do you think?" → meal_suggestion) | Low / mild | Intent classifier uses LLM — occasional misclassification is expected. User can rephrase. |

---

## Hard rules (things the agent must never do)

- **Never give a single precise protein number.** Always a range (e.g. "about 35–45g").
- **Never log a meal it couldn't clearly identify from the photo.**
- **Never save a correction without confirming with the user first.**
- **Never suggest a snack before asking about dinner plans** — risk of overshooting the goal.
- **Never handle medical questions.** Refer to a doctor, always.
- **Never claim certainty it doesn't have.** A confident wrong answer is worse than "I'm not sure."
- **Never show an error stack trace or raw exception to the user.** Always a plain, friendly message.

---

## What the user should see when things go wrong

A short, honest, friendly message. Examples:

- *"I can't make out the food clearly — could you send another photo or describe what you ate?"*
- *"I'm having trouble right now — try again in a moment."*
- *"That's outside what I can help with — worth asking your doctor."*
- *"That number seems high — are you sure? I want to log the right amount."*

The user should never be left wondering what happened or feeling judged. When in doubt: be honest, be brief, and give them a clear next step.
