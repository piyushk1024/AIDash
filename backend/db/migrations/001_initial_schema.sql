CREATE TABLE IF NOT EXISTS dataset_semantics (
    dataset_id      VARCHAR PRIMARY KEY,
    business_hint   VARCHAR,
    inferred_at     TIMESTAMP DEFAULT NOW(),
    semantics_json  JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_plans (
    plan_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      VARCHAR NOT NULL REFERENCES dataset_semantics(dataset_id),
    created_at      TIMESTAMP DEFAULT NOW(),
    plan_json       JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dashboard_plans_dataset_id
    ON dashboard_plans(dataset_id);