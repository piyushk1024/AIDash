-- Dasher schema, flattened from the original 10 incremental migrations
-- (Metabase-era columns and public_url already retired, not carried forward).

CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    username        TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'editor',
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset_metadata (
    dataset_id          TEXT PRIMARY KEY,
    table_name          TEXT NOT NULL,
    field_map           JSONB,
    user_id             TEXT NOT NULL,
    name                TEXT,
    comment             TEXT,
    original_filename   TEXT,
    file_checksum       TEXT,
    profile_json        JSONB,
    published           BOOLEAN DEFAULT false,
    published_mode      TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_metadata_user_id
    ON dataset_metadata(user_id);

-- Per-user uniqueness on checksum — two different users may upload the same file.
CREATE UNIQUE INDEX IF NOT EXISTS idx_dataset_metadata_checksum_user
    ON dataset_metadata(file_checksum, user_id)
    WHERE file_checksum IS NOT NULL;

CREATE TABLE IF NOT EXISTS dataset_semantics (
    dataset_id      VARCHAR PRIMARY KEY,
    business_hint   VARCHAR,
    inferred_at     TIMESTAMP DEFAULT NOW(),
    semantics_json  JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_plans (
    plan_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id          VARCHAR NOT NULL REFERENCES dataset_semantics(dataset_id),
    created_at          TIMESTAMP DEFAULT NOW(),
    plan_json           JSONB NOT NULL,
    stale               BOOLEAN DEFAULT false,
    generation_counter  INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_dashboard_plans_dataset_id
    ON dashboard_plans(dataset_id);

CREATE TABLE IF NOT EXISTS dataset_insights (
    insight_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    insights_json   JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_insights_dataset_id
    ON dataset_insights(dataset_id);

CREATE TABLE IF NOT EXISTS published_snapshots (
    dataset_id      TEXT NOT NULL,
    mode            TEXT NOT NULL,
    snapshot_json   JSONB NOT NULL,
    published_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset_id, mode)
);