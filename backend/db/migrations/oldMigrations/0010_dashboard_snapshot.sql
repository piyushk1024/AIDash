-- Stores dashboard snapshots for public sharing

CREATE TABLE published_snapshots (
    dataset_id   TEXT NOT NULL,
    mode         TEXT NOT NULL,
    snapshot_json JSONB NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset_id, mode)
);