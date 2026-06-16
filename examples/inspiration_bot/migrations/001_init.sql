-- Inspiration Bot — initial schema.
-- Tables are prefixed `inspo_` so they don't collide with other projects sharing
-- this database (the shared-database convention in CLAUDE.md).

CREATE TABLE IF NOT EXISTS inspo_users (
    telegram_id   BIGINT      PRIMARY KEY,           -- Telegram's verified user id (our identity)
    username      TEXT,
    first_name    TEXT,
    profile       TEXT        NOT NULL DEFAULT '',   -- the evolving "what inspires you" summary
    send_hour     INT         NOT NULL DEFAULT 8,    -- local hour to nudge, 0-23
    timezone      TEXT        NOT NULL DEFAULT 'UTC', -- IANA name, e.g. 'Europe/Berlin'
    cadence       TEXT        NOT NULL DEFAULT 'daily', -- 'daily' | 'weekdays' | 'weekly'
    paused        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_sent_at  TIMESTAMPTZ                         -- when we last nudged (keeps the tick idempotent)
);

CREATE TABLE IF NOT EXISTS inspo_items (
    id          BIGSERIAL   PRIMARY KEY,
    telegram_id BIGINT      NOT NULL REFERENCES inspo_users(telegram_id) ON DELETE CASCADE,
    kind        TEXT        NOT NULL,                -- 'photo' | 'text'
    content     TEXT        NOT NULL,                -- the text, or a description of the photo
    image_key   TEXT,                                -- R2 key when kind = 'photo'
    themes      TEXT[]      NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inspo_items_user ON inspo_items (telegram_id, created_at DESC);

CREATE TABLE IF NOT EXISTS inspo_sends (
    id          BIGSERIAL   PRIMARY KEY,
    telegram_id BIGINT      NOT NULL REFERENCES inspo_users(telegram_id) ON DELETE CASCADE,
    body        TEXT        NOT NULL,                -- what we sent (so we don't repeat it)
    image_key   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS inspo_sends_user ON inspo_sends (telegram_id, created_at DESC);
