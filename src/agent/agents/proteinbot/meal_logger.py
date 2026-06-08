"""Write and read meal entries in the database."""

from agent.services import db

from .models import MealEntry


async def log_meal(
    telegram_id: int,
    description: str,
    protein_min_g: int,
    protein_max_g: int,
    recipe_id: int | None = None,
) -> int:
    """Insert a meal and return its new id."""
    row = await db.fetchrow(
        """
        INSERT INTO proteinbot_meals
            (telegram_id, description, protein_min_g, protein_max_g, recipe_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        telegram_id,
        description,
        protein_min_g,
        protein_max_g,
        recipe_id,
    )
    assert row is not None
    return int(row["id"])


async def get_meal(meal_id: int) -> MealEntry | None:
    row = await db.fetchrow("SELECT * FROM proteinbot_meals WHERE id = $1", meal_id)
    if row is None:
        return None
    return MealEntry(**dict(row))
