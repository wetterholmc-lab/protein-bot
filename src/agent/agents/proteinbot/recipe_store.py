"""Save and retrieve named recipes."""

import json

from agent.services import db


async def save_recipe(
    telegram_id: int,
    name: str,
    ingredients: list[dict[str, str | float]],
    portions: int,
    protein_per_portion_min_g: int,
    protein_per_portion_max_g: int,
) -> int:
    """Insert a recipe and return its id."""
    row = await db.fetchrow(
        """
        INSERT INTO proteinbot_recipes
            (telegram_id, name, ingredients, portions,
             protein_per_portion_min_g, protein_per_portion_max_g)
        VALUES ($1, $2, $3::jsonb, $4, $5, $6)
        RETURNING id
        """,
        telegram_id,
        name,
        json.dumps(ingredients),
        portions,
        protein_per_portion_min_g,
        protein_per_portion_max_g,
    )
    assert row is not None
    return int(row["id"])


async def find_recipe(telegram_id: int, name: str) -> dict | None:
    """Look up a saved recipe by name (case-insensitive, partial match)."""
    row = await db.fetchrow(
        """
        SELECT * FROM proteinbot_recipes
        WHERE telegram_id = $1 AND lower(name) LIKE $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        telegram_id,
        f"%{name.lower()}%",
    )
    return dict(row) if row else None
