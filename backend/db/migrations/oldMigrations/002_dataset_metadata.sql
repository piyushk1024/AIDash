CREATE TABLE IF NOT EXISTS dataset_metadata (
    dataset_id              TEXT PRIMARY KEY,
    table_name              TEXT NOT NULL,
    metabase_table_id       INTEGER,
    field_map               JSONB,
    metabase_dashboard_id   INTEGER,
    public_url              TEXT,
    user_id                 TEXT NOT NULL,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_metadata_user_id
    ON dataset_metadata(user_id);