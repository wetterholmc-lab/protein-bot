"""Production entrypoint: a FastAPI app hosting the Telegram *webhook* and the *cron tick*.

    uv run fastapi run examples/inspiration_bot/app.py     # production (reads $PORT itself)
    uv run fastapi dev  examples/inspiration_bot/app.py     # local, only if you want webhook mode

Locally you'll normally use polling instead (python -m examples.inspiration_bot.bot); this
file is what Railway runs. Two endpoints, both protected by a shared secret:
  - POST /telegram/<token>  — Telegram delivers updates here (verified by a secret header)
  - POST /cron/tick         — the hourly scheduler calls this; it sends to whoever is due
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from loguru import logger
from telegram import Update
from telegram.ext import Application

from agent.config import get_settings
from agent.logging_setup import setup_logging
from examples.inspiration_bot.bot import build_application, post_init
from examples.inspiration_bot.jobs import run_due_sends

_ptb: Application | None = None  # the python-telegram-bot Application, built on startup


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _ptb
    setup_logging()
    settings = get_settings()
    ptb = build_application()  # local keeps a non-None type; the global is for the handlers
    _ptb = ptb
    await ptb.initialize()
    # PTB only auto-runs post_init from run_polling/run_webhook; we drive the Application
    # manually here, so call it ourselves — otherwise migrations never run in production.
    await post_init(ptb)
    await ptb.start()
    if settings.public_url and settings.telegram_bot_token:
        url = f"{settings.public_url.rstrip('/')}/telegram/{settings.telegram_bot_token}"
        await ptb.bot.set_webhook(
            url=url,
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=Update.ALL_TYPES,
        )
        # NB: `url` contains the bot token (it's the secret path), so never log it —
        # log the shape only. Same rule as logging_setup's diagnose=False.
        logger.info("webhook registered at {}/telegram/<token>", settings.public_url.rstrip("/"))
    else:
        logger.warning("PUBLIC_URL not set — webhook not registered (fine for local dev)")
    yield
    await ptb.stop()
    await ptb.shutdown()


app = FastAPI(title="Inspiration Bot", lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram/{token}")
async def telegram_webhook(
    token: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """Receive one update from Telegram and hand it to python-telegram-bot.

    Two cheap forgery checks: the path token must be our bot token, and the secret
    header Telegram echoes must match the one we registered.
    """
    settings = get_settings()
    if not settings.telegram_bot_token or not secrets.compare_digest(
        token, settings.telegram_bot_token
    ):
        raise HTTPException(status_code=404)
    if settings.telegram_webhook_secret and not secrets.compare_digest(
        x_telegram_bot_api_secret_token or "", settings.telegram_webhook_secret
    ):
        raise HTTPException(status_code=403)
    ptb = _ptb
    if ptb is None:
        raise HTTPException(status_code=503)
    update = Update.de_json(await request.json(), ptb.bot)
    if update is not None:
        await ptb.process_update(update)
    return {"ok": True}


@app.post("/cron/tick")
async def cron_tick(x_cron_secret: str | None = Header(default=None)) -> dict[str, int]:
    """Called hourly by the scheduler. Sends a nudge to every user who is due now."""
    settings = get_settings()
    if not settings.cron_secret or not secrets.compare_digest(
        x_cron_secret or "", settings.cron_secret
    ):
        raise HTTPException(status_code=401)
    ptb = _ptb
    if ptb is None:
        raise HTTPException(status_code=503)
    sent = await run_due_sends(ptb.bot)  # force=False → honour each user's schedule
    return {"sent": sent}
