"""The proactive send: turn a due user into a delivered nudge.

`is_due` is a pure function (unit-tested offline). `run_due_sends` loops active users,
sends to the ones due now, and isolates failures so one bad profile can't stop the rest.
This is the "frequent tick + per-user due-check" pattern: the scheduler fires hourly and
this code decides who actually gets a message.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger
from telegram import Bot

from agent.config import get_settings
from agent.services import media
from examples.inspiration_bot import store
from examples.inspiration_bot.agent import make_nudge


def is_due(user: store.User, now_local: datetime) -> bool:
    """Should this user get a nudge at `now_local` (their own local time)?

    True only if: not paused, it's their send hour, their cadence allows today, and we
    haven't already sent them one today. That last check keeps a re-fired tick idempotent.
    """
    if user.paused or now_local.hour != user.send_hour:
        return False
    weekday = now_local.weekday()  # Monday = 0
    if user.cadence == "weekdays" and weekday >= 5:
        return False
    if user.cadence == "weekly" and weekday != 0:  # weekly = Mondays
        return False
    if user.last_sent_at is not None:
        last_local = user.last_sent_at.astimezone(now_local.tzinfo)
        if last_local.date() == now_local.date():  # already sent today
            return False
    return True


async def generate_for_user(bot: Bot, user: store.User) -> None:
    """Generate one nudge and deliver it. Raises on failure (callers isolate)."""
    today = datetime.now(ZoneInfo(user.timezone)).strftime("%A, %d %B %Y")
    logger.info("generating nudge for user {} ({})", user.telegram_id, user.username)
    nudge = await make_nudge(user, today)  # this is the slow bit: LLM + tool calls
    logger.info("nudge ready for {} (want_image={})", user.telegram_id, nudge.want_image)

    image_key: str | None = None
    # Image generation is the one metered step — orchestrated here, not a model tool,
    # and only when fal is configured.
    if nudge.want_image and nudge.image_prompt and get_settings().fal_key:
        logger.info("generating image for {}: {!r}", user.telegram_id, nudge.image_prompt)
        result = await media.text_to_image(nudge.image_prompt, persist=True, prefix="inspo")
        if result.files:
            await bot.send_photo(
                chat_id=user.telegram_id, photo=result.files[0].url, caption=nudge.message
            )
            image_key = result.files[0].stored_key
        else:
            await bot.send_message(chat_id=user.telegram_id, text=nudge.message)
    else:
        await bot.send_message(chat_id=user.telegram_id, text=nudge.message)

    await store.record_send(user.telegram_id, nudge.message, image_key)
    await store.mark_sent(user.telegram_id)
    logger.info("delivered nudge to {} (image={})", user.telegram_id, image_key is not None)


async def run_due_sends(bot: Bot, *, force: bool = False) -> int:
    """Send a nudge to every active user who is due now. Returns how many were sent.

    `force=True` ignores the clock (used by the local `inspo-cron` trigger so you can
    see it work immediately); production passes force=False so the schedule is honoured.
    """
    sent = 0
    for user in await store.active_users():
        now_local = datetime.now(ZoneInfo(user.timezone))
        if not force and not is_due(user, now_local):
            continue
        try:
            await generate_for_user(bot, user)
            sent += 1
        except Exception:  # noqa: BLE001 — one user's failure must not stop the rest
            logger.exception("nudge failed for user {}", user.telegram_id)
    return sent
