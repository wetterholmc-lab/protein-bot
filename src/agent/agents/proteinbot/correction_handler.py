"""Apply a user correction to a previously logged meal."""

from agent.services import db


async def apply_correction(meal_id: int, corrected_protein_g: int) -> None:
    """Overwrite the protein value for a meal with the user-supplied figure."""
    await db.execute(
        "UPDATE proteinbot_meals SET protein_actual_g = $1 WHERE id = $2",
        corrected_protein_g,
        meal_id,
    )
