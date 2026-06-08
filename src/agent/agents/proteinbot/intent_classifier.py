"""Classify the intent of a free-text message from the user."""

from pydantic_ai import Agent

from agent.services.llm import build_model

from .models import IntentResult

_SYSTEM_PROMPT = """
You classify messages sent to a protein-tracking Telegram bot into one of four intents.
Messages may be in any language — classify them regardless of language.

- status: the user wants to know how much protein they have logged today and how much
  is left (e.g. "status", "how am I doing?", "what's left?", "hur ligger jag till?",
  "combien j'ai mangé?", "wie viel habe ich heute?")

- correction: the user is correcting a previous protein estimate
  (e.g. "no, it was 40g", "actually more like 30 grams", "closer to 50g",
  "nej, det var 40g", "non, c'était 40g")
  Extract the corrected value in grams as correction_g.

- meal_suggestion: the user wants food suggestions for a specific upcoming meal
  (e.g. "what should I eat for lunch?", "suggest dinner", "vad ska jag äta till middag?",
  "lunch ideas", "förslag på frukost", "que manger ce soir?")
  Extract the meal type as meal_type in English and lowercase (e.g. "lunch", "dinner",
  "breakfast", "snack").

- off_topic: anything that doesn't fit the above

Return the intent and, for corrections, the corrected gram value; for meal suggestions,
the meal type in English and lowercase.
""".strip()

_agent: Agent[None, IntentResult] = Agent(
    build_model("fast"),
    output_type=IntentResult,
    system_prompt=_SYSTEM_PROMPT,
)


async def classify(text: str) -> IntentResult:
    """Return the intent of a user message."""
    result = await _agent.run(text)
    return result.output


def is_status_request(text: str) -> bool:
    """Quick heuristic check before calling the LLM — avoids a round-trip for obvious cases."""
    lower = text.lower().strip()
    keywords = {
        "status",
        "how am i doing",
        "what's left",
        "how much",  # English
        "hur ligger",
        "vad saknas",
        "hur mycket",  # Swedish
        "combien",
        "qu'est-ce que j'ai",  # French
        "wie viel",
        "was habe ich",  # German
        "cuánto",
        "cuanto",  # Spanish
    }
    return any(k in lower for k in keywords)
