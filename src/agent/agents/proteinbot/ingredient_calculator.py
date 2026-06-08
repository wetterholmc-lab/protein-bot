"""Calculate protein per portion from a free-text ingredient description."""

from pydantic import BaseModel
from pydantic_ai import Agent

from agent.services.llm import build_model

_SYSTEM_PROMPT = """
You are a nutrition expert. Given a list of ingredients with approximate quantities
and a number of portions, calculate the total protein and return a range per portion.
Ingredient lists may be in any language — handle them regardless of language.

Rules:
- Return a range (min/max), not a single precise number.
- Account for cooking losses where relevant (e.g. meat shrinks ~25% when cooked).
- If quantities are vague ("a handful", "some", "en näve"), use a reasonable middle
  estimate and widen the range.
- Write the description in English.
""".strip()


class IngredientResult(BaseModel):
    protein_per_portion_min_g: int
    protein_per_portion_max_g: int
    description: str  # short human-readable summary, e.g. "lentil soup (4 portions)"


_agent: Agent[None, IngredientResult] = Agent(
    build_model("fast"),
    output_type=IngredientResult,
    system_prompt=_SYSTEM_PROMPT,
)


async def calculate_from_ingredients(ingredients_text: str, portions: int) -> IngredientResult:
    """Parse a free-text ingredient list and return protein per portion."""
    result = await _agent.run(
        f"Ingredients: {ingredients_text}\nPortions: {portions}\nCalculate protein per portion."
    )
    return result.output
