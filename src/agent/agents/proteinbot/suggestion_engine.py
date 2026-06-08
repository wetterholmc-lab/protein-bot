"""Generate protein-rich food suggestions and contextual meal feedback."""

from datetime import datetime

from pydantic_ai import Agent

from agent.services.llm import build_model

from .models import DietStyle

_SYSTEM_PROMPT = """
You are a helpful nutrition assistant for a protein-tracking bot. Your messages are
short Telegram chat messages — 2–4 sentences maximum.

Rules:
- Always give concrete, everyday foods with approximate protein per serving in parentheses.
- Match the diet style strictly: no meat for vegetarian/vegan, no animal products for vegan.
- Format food suggestions on their own line starting with a dash.
- Never lecture or moralize. Be warm, practical, and direct.
""".strip()

_agent: Agent[None, str] = Agent(
    build_model("fast"),
    output_type=str,
    system_prompt=_SYSTEM_PROMPT,
)

# Expected cumulative protein as a fraction of daily goal by time of day.
# Used to assess whether the current total is on track.
_EXPECTED_BY_HOUR: dict[int, float] = {
    6: 0.0,
    9: 0.20,  # after breakfast
    11: 0.25,
    13: 0.50,  # after lunch
    15: 0.55,
    17: 0.65,  # after afternoon snack
    20: 0.90,  # after dinner
    23: 1.00,
}


def _expected_fraction(hour: int) -> float:
    """Interpolate the expected fraction of daily goal for a given hour."""
    keys = sorted(_EXPECTED_BY_HOUR)
    for i, k in enumerate(keys):
        if hour <= k:
            if i == 0:
                return _EXPECTED_BY_HOUR[k]
            prev = keys[i - 1]
            # Linear interpolation between the two nearest checkpoints.
            t = (hour - prev) / (k - prev)
            return _EXPECTED_BY_HOUR[prev] + t * (_EXPECTED_BY_HOUR[k] - _EXPECTED_BY_HOUR[prev])
    return 1.0


def _time_of_day_label(hour: int) -> str:
    if hour < 10:
        return "breakfast"
    if hour < 14:
        return "lunch"
    if hour < 17:
        return "an afternoon snack"
    return "dinner"


async def feedback_after_meal(
    meal_description: str,
    meal_protein_min: int,
    meal_protein_max: int,
    total_today_g: int,
    goal_g: int,
    diet_style: DietStyle,
    now: datetime | None = None,
) -> str:
    """Return a short contextual comment on a just-logged meal.

    Tells the user whether their current daily total is on track for the time
    of day, and suggests additions if it's low.
    """
    now = now or datetime.now()
    hour = now.hour
    meal_label = _time_of_day_label(hour)
    expected_g = round(_expected_fraction(hour) * goal_g)
    deficit_g = goal_g - total_today_g

    prompt = (
        f"The user just logged {meal_description} "
        f"(~{meal_protein_min}–{meal_protein_max}g protein) as {meal_label}. "
        f"Their total today is now {total_today_g}g of their {goal_g}g goal "
        f"({deficit_g}g remaining). At this time of day they would typically expect "
        f"to have around {expected_g}g logged. Diet style: {diet_style.value}.\n\n"
        "Give a 1–2 sentence comment on whether this is on track, a bit low, or a "
        "great start. If it's low, add 1–2 concrete suggestions for what to add."
    )
    result = await _agent.run(prompt)
    return result.output


async def suggest_for_meal(
    meal_name: str,
    remaining_g: int,
    diet_style: DietStyle,
) -> str:
    """Suggest what to eat for a specific upcoming meal to stay on track."""
    result = await _agent.run(
        f"The user wants suggestions for {meal_name}. "
        f"They still need about {remaining_g}g of protein today. Diet: {diet_style.value}. "
        f"Suggest 2–3 {meal_name} options that would make a meaningful dent in that, "
        "with approximate protein per serving."
    )
    return result.output


async def suggest_dinner(deficit_g: int, diet_style: DietStyle) -> str:
    """Return dinner suggestions that cover most of the deficit."""
    result = await _agent.run(
        f"Protein deficit: {deficit_g}g. Diet: {diet_style.value}. "
        "Suggest 2–3 dinner options that would cover most of this deficit."
    )
    return result.output


async def suggest_snacks(deficit_g: int, diet_style: DietStyle) -> str:
    """Return snack suggestions for a smaller gap."""
    result = await _agent.run(
        f"Protein deficit: {deficit_g}g. Diet: {diet_style.value}. "
        "Suggest 2–3 high-protein snack options."
    )
    return result.output
