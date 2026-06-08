# Scenarios

**Stage 3 — Concrete end-to-end walkthroughs.** These are what you'll test against
later (stage 8). Write them as real, specific stories — actual example inputs and the
output you'd expect.

---

## Happy paths

### 0. Onboarding — custom protein goal
1. Caroline completes the onboarding questions (age, weight, height, etc.).
2. The agent replies: "Based on your profile, I suggest **110g** of protein per day.
   Would you like to use this, or set your own goal?" with two buttons.
3. Caroline taps "Set my own" and types "130".
4. The agent replies: "Got it — your daily protein goal is set to 130g."

**Expected result:** The saved goal is 130g, not the calculated 110g. The suggested
value is always shown so the user has a reference point.

---

### 0b. Onboarding — perimenopause question
1. Caroline (46 years old, female) completes the onboarding.
2. After answering "No" to the pregnant/breastfeeding question, the agent asks:
   "Are you in perimenopause or menopause? This affects protein needs."
3. Caroline answers "Yes".
4. The suggested protein goal is 15g higher than it would otherwise be.

**Expected result:** Question only appears for females aged 40+ who are not pregnant.
Males, "other" sex, and pregnant users skip it.

---

### 1. Photo of simple food — with contextual feedback
1. Caroline sends a photo of scrambled eggs at 8am. Goal: 110g.
2. The agent replies: "Logged: scrambled eggs — about 18–24g protein.
   Total today: 21g of your 110g goal.
   That's a solid breakfast — you're on track for the morning. To boost it a bit,
   add a slice of smoked salmon (~10g) or some cottage cheese on the side (~12g)."

**Expected result:** A protein range (never a single precise number), the running daily
total, and a short contextual comment on whether the amount is appropriate for the time
of day. If low, 1–2 concrete additions are suggested.

---

### 2. Home-cooked food — ingredient walkthrough
1. Caroline sends a photo of a pot of lentil soup.
2. The agent recognises it's home-cooked and asks: "Looks like lentil soup — want to tell
   me roughly what went into it and how many portions? I'll calculate protein per serving."
3. Caroline replies: "Red lentils 400g, chicken stock, one onion. Made 4 portions."
4. The agent calculates and replies: "About 18–22g protein per portion. Logged 1 portion.
   Total today: 83g of your 110g goal. Want me to save this recipe for next time?"
5. Caroline says yes. The recipe is saved.

**Expected result:** Per-portion protein estimate, daily total updated, recipe saved for
reuse.

---

### 3. Status check at any time
1. Caroline types "status" (or "how am I doing?", "what's left?", "hur ligger jag till?" —
   the bot understands natural language, not just exact commands).
2. The agent replies: "So far today: 83g protein of your 110g goal. You have about 27g left.
   Logged meals: scrambled eggs (morning), chicken and rice (lunch), lentil soup (afternoon)."

**Expected result:** Clear summary of total eaten, goal, remainder, and what was logged —
available any time on demand.

---

### 4. 15:00 reminder — protein missing
1. At 15:00, Caroline has logged 60g out of 110g.
2. The agent sends: "Afternoon check-in — you're at 60g of your 110g goal. Still 50g to go.
   Are you planning dinner tonight?"
3. Caroline replies "yes".
4. The agent replies: "Great — here are some dinner ideas that would get you close:
   - Salmon fillet with veg (~35g)
   - Chicken stir-fry (~40g)
   - Lentil dal (~22g)
   If dinner doesn't quite cover it, a Greek yoghurt afterwards (~15g) would close the gap."

**Expected result:** Concrete, inspiring suggestions tailored to the deficit — not generic
advice. Dinner ideas come first; a snack is only mentioned if the gap is likely to remain
after dinner. Suggestions respect the user's diet style (omnivore/vegetarian/vegan).

---

### 5. 15:00 reminder — goal already reached
1. At 15:00, Caroline has logged 115g out of 110g.
2. The agent sends: "You've already hit your protein goal for today — 115g logged. Nice work,
   nothing left to do on that front."

**Expected result:** Positive confirmation, no unnecessary reminder or snack suggestion.

---

### 9. Meal suggestion on request
1. Caroline types "what should I eat for lunch?" after logging breakfast (21g of 110g).
2. The agent replies: "You have 89g left to hit your goal today.
   Suggestions for lunch:
   - Grilled chicken salad (~40g)
   - Tuna with wholegrain crackers (~35g)
   - Greek yoghurt bowl with nuts (~25g)"

**Expected result:** Concrete suggestions for the named meal, calibrated to the remaining
deficit, respecting diet style. If the goal is already reached, says so and offers
suggestions as inspiration only.

---

## Edge cases

### 6. Unclear or blurry photo
1. Caroline sends a blurry photo where the food is hard to identify.
2. The agent replies: "I can't make out the food clearly enough to give a reliable estimate.
   Could you send another photo or describe what you ate?"

**Expected result:** Honest admission that it can't tell, with a clear ask for more info.
Never a confident guess from a bad photo.

---

### 7. Non-food photo
1. Caroline accidentally sends a photo of her desk.
2. The agent replies: "That doesn't look like food — did you mean to send a different photo?"

**Expected result:** Short, friendly clarification. No protein logged.

---

### 8. Wrong guess — correction and learning
1. Caroline logs a meal; the agent estimates 20–28g protein.
2. Caroline replies: "No, it was more like 40g — I used a lot of chicken."
3. The agent replies: "Got it, I'll update that to 40g. Noted for next time you log something
   similar. Total today: 95g of your 110g goal."
4. The correction is saved in the database and used as a reference for future similar meals.

**Expected result:** Correction accepted gracefully, confirmed before saving, daily total
recalculated, preference remembered.

---

## Done = all scenarios pass

When every scenario here behaves as written, the agent is working. Keep this list up to
date as you discover new cases during testing — add them, then make them pass.
