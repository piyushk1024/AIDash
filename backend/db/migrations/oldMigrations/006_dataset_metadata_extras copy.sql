-- Adds three columns to dataset_metadata as part of the Step 1 backend pre-work.
--
-- original_filename: stores the user-facing CSV filename so the sidebar can
--   display it without having to glob the upload directory.
--
-- file_checksum: SHA-256 of the uploaded file bytes. Used to 409 on duplicate
--   uploads per user. The partial unique index enforces this at the DB level.
--   NULL for datasets uploaded before this migration.
--
-- profile_json: cached output of profile_csv(). Once populated, downstream
--   routes (semantics, planner, agent) read from here instead of re-reading
--   the CSV from disk. Foundational step toward not needing the CSV post-upload.

ALTER TABLE dataset_metadata
ADD COLUMN IF NOT EXISTS original_filename  TEXT,
ADD COLUMN IF NOT EXISTS file_checksum      TEXT,
ADD COLUMN IF NOT EXISTS profile_json       JSONB;

-- Per-user uniqueness on checksum — two different users may upload the same file.
-- Partial index excludes NULL rows so pre-migration data is unaffected.
CREATE UNIQUE INDEX IF NOT EXISTS idx_dataset_metadata_checksum_user
    ON dataset_metadata(file_checksum, user_id)
    WHERE file_checksum IS NOT NULL;