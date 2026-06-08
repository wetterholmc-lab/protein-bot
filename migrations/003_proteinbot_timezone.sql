-- Add per-user timezone offset and reminder tracking.
ALTER TABLE proteinbot_users
    ADD COLUMN IF NOT EXISTS timezone_offset smallint NOT NULL DEFAULT 1;

-- Track the last date a reminder was sent to avoid double-sends when the
-- hourly job restarts mid-hour.
ALTER TABLE proteinbot_users
    ADD COLUMN IF NOT EXISTS last_reminded_date date;
