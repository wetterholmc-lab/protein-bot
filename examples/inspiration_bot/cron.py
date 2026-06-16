"""The proactive loop's command-line entrypoint — your "cron".

    uv run python -m examples.inspiration_bot.cron

In **development** it sends a nudge to every active user *now*, so you can see the
morning behaviour without waiting for the morning. In **production** (ENVIRONMENT=
production) it honours each user's schedule instead — so a Railway Cron service can run
this same command hourly and only the users who are due will get a message.

(There's also a protected POST /cron/tick endpoint in app.py for HTTP schedulers and for
triggering a tick by hand — both run the same `run_due_sends` logic.)
"""

from __future__ import annotations

import asyncio

from loguru import logger
from telegram import Bot

from agent.config import get_settings
from agent.logging_setup import setup_logging
from agent.services import db
from examples.inspiration_bot.jobs import run_due_sends


async def _run() -> None:
    token = get_settings().telegram_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Add your @BotFather token to .env.")
    # Dev: fire now so you can see it work. Prod: honour each user's schedule.
    force = not get_settings().is_production
    async with Bot(token) as bot:
        sent = await run_due_sends(bot, force=force)
    logger.info("sent {} nudge(s)", sent)
    await db.close_pool()


def main() -> None:
    setup_logging()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
