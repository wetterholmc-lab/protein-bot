"""Read today's meals and compute the daily protein summary."""

from datetime import date

from agent.services import db

from .models import DailySummary, MealEntry, UserProfile


async def get_daily_summary(profile: UserProfile, for_date: date | None = None) -> DailySummary:
    """Return today's protein total and deficit for a user."""
    target = for_date or date.today()
    rows = await db.fetch(
        """
        SELECT * FROM proteinbot_meals
        WHERE telegram_id = $1
          AND logged_at::date = $2
        ORDER BY logged_at
        """,
        profile.telegram_id,
        target,
    )
    meals = [MealEntry(**dict(r)) for r in rows]
    total_g = sum(m.effective_protein_g for m in meals)
    deficit_g = profile.protein_goal_g - total_g
    return DailySummary(
        total_g=total_g,
        goal_g=profile.protein_goal_g,
        deficit_g=deficit_g,
        meals=meals,
    )


def format_summary(summary: DailySummary) -> str:
    """Return a short Telegram-friendly status message."""
    if summary.deficit_g <= 0:
        return (
            f"You've hit your protein goal for today — {summary.total_g}g logged "
            f"(goal: {summary.goal_g}g). Nice work!"
        )
    lines = [
        f"Today so far: *{summary.total_g}g* of your *{summary.goal_g}g* goal. "
        f"About *{summary.deficit_g}g* to go.",
    ]
    if summary.meals:
        meal_list = ", ".join(m.description for m in summary.meals)
        lines.append(f"Logged: {meal_list}.")
    else:
        lines.append("Nothing logged yet today.")
    return "\n".join(lines)
