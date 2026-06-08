CREATE TABLE IF NOT EXISTS proteinbot_authorized (
    telegram_id BIGINT PRIMARY KEY,
    authorized_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grandfather in anyone who already has a profile so they aren't locked out.
INSERT INTO proteinbot_authorized (telegram_id)
SELECT telegram_id FROM proteinbot_users
ON CONFLICT DO NOTHING;
