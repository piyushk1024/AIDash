-- Migration 001: Initial schema
-- Run this to recreate the database from scratch

-- Dataset semantics: stores LLM inference results per dataset
CREATE TABLE IF NOT EXISTS dataset_semantics (
    dataset_id      VARCHAR PRIMARY KEY,
    business_hint   VARCHAR,
    inferred_at     TIMESTAMP DEFAULT NOW(),
    semantics_json  JSONB NOT NULL
);

-- Dashboard plans: stores generated chart plans per dataset
CREATE TABLE IF NOT EXISTS dashboard_plans (
    plan_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      VARCHAR NOT NULL REFERENCES dataset_semantics(dataset_id),
    created_at      TIMESTAMP DEFAULT NOW(),
    plan_json       JSONB NOT NULL
);

-- Index for fast lookup by dataset_id on dashboard_plans
CREATE INDEX IF NOT EXISTS idx_dashboard_plans_dataset_id 
    ON dashboard_plans(dataset_id);