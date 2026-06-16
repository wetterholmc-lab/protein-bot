"""The proactive generator agent — composes one personal nudge using tools.

This is the example's centrepiece for *tool use* and *safe scoping*:

  - The agent has read tools (look at what the user saved / what we sent) and one
    reversible write tool (set_schedule). It has NO destructive or metered tool —
    deleting is a human-confirmed command, image generation is orchestrated in jobs.py.
  - The current user's id is carried in `Deps` and injected via `deps=` at run time.
    Tools read `ctx.deps.telegram_id`. The model can NEVER pass another user's id,
    because the id isn't a tool argument at all — scoping is structural, not a prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import available_timezones

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from agent.services.llm import build_model, research
from examples.inspiration_bot import store


@dataclass
class Deps:
    """Injected per run. The model never sees or sets this — we pass it via deps=."""

    telegram_id: int


class Nudge(BaseModel):
    message: str = Field(description="The short, personal nudge to send (1-4 sentences).")
    want_image: bool = Field(
        description="True only if a generated image would genuinely add to it."
    )
    image_prompt: str | None = Field(
        default=None, description="If want_image, a vivid prompt for the image."
    )


# "balanced" keeps each send cheap; bump to "smart" for richer nudges (costs more).
generator = Agent(
    build_model("balanced"),
    deps_type=Deps,
    output_type=Nudge,
    system_prompt=(
        "You are an inspiring friend with great taste. Using your tools, look at what this person "
        "has saved and what you've already sent them, then craft ONE short, personal nudge for "
        "today — a reflection, a prompt, or a fresh discovery that fits their taste. "
        "NEVER repeat something you've already sent. Optionally suggest an image only if it truly "
        "adds something. Be warm and specific; never generic."
    ),
)


def _format_items(items: list[store.Item]) -> str:
    if not items:
        return "(nothing yet)"
    return "\n".join(f"- [{', '.join(item.themes)}] {item.content}" for item in items)


@generator.tool
async def recent_items(ctx: RunContext[Deps], limit: int = 10) -> str:
    """The most recent things this person saved, with their themes."""
    return _format_items(await store.recent_items(ctx.deps.telegram_id, limit))


@generator.tool
async def search_items(ctx: RunContext[Deps], theme: str, limit: int = 10) -> str:
    """Past saved items matching a theme or keyword — to build on a recurring interest."""
    return _format_items(await store.search_items(ctx.deps.telegram_id, theme, limit))


@generator.tool
async def recent_sends(ctx: RunContext[Deps], limit: int = 10) -> str:
    """What you've already sent this person. Do NOT repeat any of these."""
    sends = await store.recent_sends(ctx.deps.telegram_id, limit)
    return "\n".join(f"- {send.body}" for send in sends) or "(nothing sent yet)"


# tool_plain: this one needs no user context (it just searches the web), so it takes
# no RunContext — unlike the scoped tools above.
@generator.tool_plain
async def web_search(query: str) -> str:
    """Search the live web (Perplexity) for something fresh and real. Returns text + sources."""
    found = await research(query)
    sources = "\n".join(f"  - {source.url}" for source in found.sources)
    return f"{found.text}\n\nSources:\n{sources}" if sources else found.text


@generator.tool
async def check_schedule(ctx: RunContext[Deps]) -> str:
    """When and how often this person currently gets nudged."""
    user = await store.get_user(ctx.deps.telegram_id)
    if user is None:
        return "unknown"
    if user.paused:
        return "paused"
    return f"{user.cadence} around {user.send_hour:02d}:00 {user.timezone}"


def validate_schedule(
    send_hour: int | None, timezone: str | None, cadence: str | None
) -> tuple[bool, str]:
    """Pure validation for a schedule change (also unit-tested offline)."""
    if send_hour is not None and not 0 <= send_hour <= 23:
        return False, "hour must be between 0 and 23"
    if cadence is not None and cadence not in store.CADENCES:
        return False, f"cadence must be one of {', '.join(store.CADENCES)}"
    if timezone is not None and timezone not in available_timezones():
        return False, "unknown timezone — use an IANA name like 'Europe/Berlin'"
    return True, ""


@generator.tool
async def set_schedule(
    ctx: RunContext[Deps],
    send_hour: int | None = None,
    timezone: str | None = None,
    cadence: str | None = None,
    paused: bool | None = None,
) -> str:
    """Change this person's nudge schedule.

    hour 0-23; timezone an IANA name; cadence daily|weekdays|weekly. Ask the user for
    their city/timezone if you need it — don't guess a timezone.
    """
    ok, problem = validate_schedule(send_hour, timezone, cadence)
    if not ok:
        return f"Not changed: {problem}"
    await store.set_schedule(
        ctx.deps.telegram_id,
        send_hour=send_hour,
        timezone=timezone,
        cadence=cadence,
        paused=paused,
    )
    return "Schedule updated."


async def make_nudge(user: store.User, today: str) -> Nudge:
    """Run the generator agent for one user. `today` is their local date as a string."""
    prompt = (
        f"Today is {today}. Here is what you know about this person:\n"
        f"{user.profile or '(you barely know them yet — be welcoming and curious)'}\n\n"
        "Craft today's nudge. Use your tools to look at what they've saved and what you've "
        "already sent, so you stay personal and never repeat yourself."
    )
    result = await generator.run(prompt, deps=Deps(user.telegram_id))
    return result.output
