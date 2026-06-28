ALTER TABLE proteinbot_users
    ADD COLUMN IF NOT EXISTS reminder_status TEXT NOT NULL DEFAULT 'active';
