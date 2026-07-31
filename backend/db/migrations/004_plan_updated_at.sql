ALTER TABLE dataset_metadata
    ADD COLUMN IF NOT EXISTS last_active_mode TEXT;