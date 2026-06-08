"""Analyse a food photo and estimate its protein content using a vision model."""

from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

from agent.services.llm import build_model

from .models import FoodEstimate

_SYSTEM_PROMPT = """
You are a nutrition expert who estimates protein content from food photos.

Rules:
- Always return a range, never a single precise number (protein_min_g and protein_max_g).
- A typical portion size is what a person would eat in one sitting.
- If the dish looks home-cooked or complex (stew, soup, pasta), set is_home_cooked=true
  so we can ask the user for ingredients.
- If you cannot identify the food (blurry, wrong angle, too dark), set is_identifiable=false
  and set protein_min_g=0, protein_max_g=0.
- If the image is not food at all, set is_food=false and all protein fields to 0.
- Be conservative — it is better to underestimate than to give false confidence.
""".strip()

_agent: Agent[None, FoodEstimate] = Agent(
    build_model("balanced"),
    output_type=FoodEstimate,
    system_prompt=_SYSTEM_PROMPT,
)


async def analyze_food_photo(photo_bytes: bytes) -> FoodEstimate:
    """Return a protein estimate for the food in the given photo bytes."""
    result = await _agent.run(
        [
            BinaryContent(data=photo_bytes, media_type="image/jpeg"),
            "Analyse this food photo and return a protein estimate for one portion.",
        ]
    )
    return result.output
