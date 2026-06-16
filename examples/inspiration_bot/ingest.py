"""The reactive loop: understand an incoming item, store it, evolve the profile.

Two small agents:
  - `_understand` looks at a photo (vision) or text and returns a vivid summary + themes.
  - `_profile` rewrites the user's running "what inspires you" profile, folding in the
    new item. It *rewrites* (bounded) rather than appends, so the profile can't grow forever.

It composes the starter services: `llm` (build_model) for the agents, `storage` for the
photo, and `store` for persistence.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent

from agent.services import storage
from agent.services.llm import build_model
from examples.inspiration_bot import store


class Understanding(BaseModel):
    summary: str = Field(description="One vivid sentence: what this is and its mood/aesthetic.")
    themes: list[str] = Field(
        description="1-3 short, lowercase themes, e.g. 'quiet minimalism', 'bold colour'."
    )


# balanced = Claude Sonnet, which handles both vision (photos) and text.
_understand = Agent(
    build_model("balanced"),
    output_type=Understanding,
    system_prompt=(
        "You help capture what inspires someone. Given a photo or a piece of text they saved, "
        "name in ONE vivid sentence what it is and its mood, plus 1-3 short themes. Be concrete "
        "and specific — never generic filler like 'interesting' or 'creative'."
    ),
)

_profile = Agent(
    build_model("balanced"),
    system_prompt=(
        "You maintain a short, evolving profile of what inspires a person. Given their current "
        "profile and a new thing they just saved, rewrite the profile in 2-4 sentences: keep the "
        "durable patterns, fold in the new signal, drop noise. Plain prose. No lists, no preamble."
    ),
)

_SUFFIX = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


async def _understand_photo(image: bytes, media_type: str) -> Understanding:
    result = await _understand.run(
        [
            "I just saved this image because it inspired me — capture it.",
            BinaryContent(data=image, media_type=media_type),
        ]
    )
    return result.output


async def _understand_text(text: str) -> Understanding:
    result = await _understand.run(f"I just saved this text because it inspired me:\n\n{text}")
    return result.output


async def _rewrite_profile(current: str, summary: str, themes: list[str]) -> str:
    result = await _profile.run(
        f"Current profile:\n{current or '(empty — this is the first thing they have saved)'}\n\n"
        f"New thing they saved: {summary} (themes: {', '.join(themes)})\n\nRewrite the profile."
    )
    return result.output.strip()


async def log_text(user: store.User, text: str) -> Understanding:
    """Understand a text item, store it, and update the profile. Returns the understanding."""
    understanding = await _understand_text(text)
    await store.add_item(user.telegram_id, kind="text", content=text, themes=understanding.themes)
    await store.update_profile(
        user.telegram_id,
        await _rewrite_profile(user.profile, understanding.summary, understanding.themes),
    )
    return understanding


async def log_photo(user: store.User, image: bytes, media_type: str) -> Understanding:
    """Understand a photo, save it to R2, store the item, and update the profile."""
    understanding = await _understand_photo(image, media_type)
    key = await storage.store_bytes(
        image, suffix=_SUFFIX.get(media_type, ".jpg"), prefix="inspo", content_type=media_type
    )
    await store.add_item(
        user.telegram_id,
        kind="photo",
        content=understanding.summary,
        themes=understanding.themes,
        image_key=key,
    )
    await store.update_profile(
        user.telegram_id,
        await _rewrite_profile(user.profile, understanding.summary, understanding.themes),
    )
    return understanding
