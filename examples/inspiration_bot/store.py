"""Database access for the Inspiration Bot — every query scoped to one `telegram_id`.

This wraps the starter's `agent.services.db` (raw asyncpg, parameterized) and maps
rows to small Pydantic models, so the rest of the code works with typed objects.

Scoping is the security backbone: a user can only ever touch their own rows, because
every function takes `telegram_id` and filters on it. The generator agent's tools get
that id by *dependency injection*, never as a model-chosen argument (see agent.py).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from agent.services import db

CADENCES = ("daily", "weekdays", "weekly")


class User(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    profile: str = ""
    send_hour: int = 8
    timezone: str = "UTC"
    cadence: str = "daily"
    paused: bool = False
    created_at: datetime | None = None
    last_sent_at: datetime | None = None


class Item(BaseModel):
    kind: str
    content: str
    image_key: str | None = None
    themes: list[str] = []
    created_at: datetime | None = None


class Send(BaseModel):
    body: str
    image_key: str | None = None
    created_at: datetime | None = None


async def upsert_user(telegram_id: int, username: str | None, first_name: str | None) -> bool:
    """Create the user on first contact, or refresh their name. Returns True if newly created.

    Two statements (check, then insert/update) is plenty for a single chatting user —
    no need for the cleverer ON CONFLICT ... RETURNING xmax trick here.
    """
    existing = await db.fetchrow("SELECT 1 FROM inspo_users WHERE telegram_id = $1", telegram_id)
    if existing is None:
        await db.execute(
            "INSERT INTO inspo_users (telegram_id, username, first_name) VALUES ($1, $2, $3)",
            telegram_id,
            username,
            first_name,
        )
        return True
    await db.execute(
        "UPDATE inspo_users SET username = $2, first_name = $3 WHERE telegram_id = $1",
        telegram_id,
        username,
        first_name,
    )
    return False


async def get_user(telegram_id: int) -> User | None:
    row = await db.fetchrow("SELECT * FROM inspo_users WHERE telegram_id = $1", telegram_id)
    return User(**dict(row)) if row else None


async def active_users() -> list[User]:
    """Every non-paused user — the candidates for a scheduled nudge."""
    rows = await db.fetch("SELECT * FROM inspo_users WHERE paused = FALSE")
    return [User(**dict(row)) for row in rows]


async def update_profile(telegram_id: int, profile: str) -> None:
    await db.execute(
        "UPDATE inspo_users SET profile = $2 WHERE telegram_id = $1", telegram_id, profile
    )


async def add_item(
    telegram_id: int,
    *,
    kind: str,
    content: str,
    themes: list[str],
    image_key: str | None = None,
) -> None:
    await db.execute(
        "INSERT INTO inspo_items (telegram_id, kind, content, image_key, themes) "
        "VALUES ($1, $2, $3, $4, $5)",
        telegram_id,
        kind,
        content,
        image_key,
        themes,
    )


async def recent_items(telegram_id: int, limit: int = 10) -> list[Item]:
    rows = await db.fetch(
        "SELECT kind, content, image_key, themes, created_at FROM inspo_items "
        "WHERE telegram_id = $1 ORDER BY created_at DESC LIMIT $2",
        telegram_id,
        limit,
    )
    return [Item(**dict(row)) for row in rows]


async def search_items(telegram_id: int, theme: str, limit: int = 10) -> list[Item]:
    """Past items whose text matches `theme` or that carry it as a tag (scoped to the user)."""
    rows = await db.fetch(
        "SELECT kind, content, image_key, themes, created_at FROM inspo_items "
        "WHERE telegram_id = $1 AND (content ILIKE $2 OR $3 = ANY(themes)) "
        "ORDER BY created_at DESC LIMIT $4",
        telegram_id,
        f"%{theme}%",
        theme,
        limit,
    )
    return [Item(**dict(row)) for row in rows]


async def item_count(telegram_id: int) -> int:
    row = await db.fetchrow(
        "SELECT count(*) AS n FROM inspo_items WHERE telegram_id = $1", telegram_id
    )
    return int(row["n"]) if row else 0


async def recent_sends(telegram_id: int, limit: int = 10) -> list[Send]:
    rows = await db.fetch(
        "SELECT body, image_key, created_at FROM inspo_sends "
        "WHERE telegram_id = $1 ORDER BY created_at DESC LIMIT $2",
        telegram_id,
        limit,
    )
    return [Send(**dict(row)) for row in rows]


async def record_send(telegram_id: int, body: str, image_key: str | None = None) -> None:
    await db.execute(
        "INSERT INTO inspo_sends (telegram_id, body, image_key) VALUES ($1, $2, $3)",
        telegram_id,
        body,
        image_key,
    )


async def mark_sent(telegram_id: int) -> None:
    await db.execute(
        "UPDATE inspo_users SET last_sent_at = now() WHERE telegram_id = $1", telegram_id
    )


async def set_schedule(
    telegram_id: int,
    *,
    send_hour: int | None = None,
    timezone: str | None = None,
    cadence: str | None = None,
    paused: bool | None = None,
) -> None:
    """Update only the schedule fields that were provided (others left unchanged)."""
    updates = {
        "send_hour": send_hour,
        "timezone": timezone,
        "cadence": cadence,
        "paused": paused,
    }
    updates = {col: val for col, val in updates.items() if val is not None}
    if not updates:
        return
    cols = list(updates)
    # Column names come from our own dict keys (never user input), so it's safe to
    # interpolate them; the *values* go through $-parameters.
    assignments = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(cols))
    await db.execute(
        f"UPDATE inspo_users SET {assignments} WHERE telegram_id = $1",
        telegram_id,
        *(updates[col] for col in cols),
    )


async def delete_everything(telegram_id: int) -> list[str]:
    """Delete the user and (via ON DELETE CASCADE) their items & sends.

    Returns the R2 image keys that the caller should also delete from storage —
    we keep storage out of this module so the DB layer stays pure DB.
    """
    rows = await db.fetch(
        "SELECT image_key FROM inspo_items WHERE telegram_id = $1 AND image_key IS NOT NULL "
        "UNION ALL "
        "SELECT image_key FROM inspo_sends WHERE telegram_id = $1 AND image_key IS NOT NULL",
        telegram_id,
    )
    keys = [row["image_key"] for row in rows]
    await db.execute("DELETE FROM inspo_users WHERE telegram_id = $1", telegram_id)  # cascades
    return keys
