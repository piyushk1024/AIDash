-- 009_llm_quota.sql

ALTER TABLE users
    ADD COLUMN daily_call_limit INTEGER;

CREATE TABLE IF NOT EXISTS daily_llm_usage (
    user_id     TEXT NOT NULL REFERENCES users(user_id),
    usage_date  DATE NOT NULL,
    calls_used  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, usage_date)
);