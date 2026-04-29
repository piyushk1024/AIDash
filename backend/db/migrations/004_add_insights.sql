-- Migration 004: Insight history
CREATE TABLE IF NOT EXISTS dataset_insights (
    insight_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id  TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    insights_json JSONB NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_insights_dataset_id
    ON dataset_insights(dataset_id);