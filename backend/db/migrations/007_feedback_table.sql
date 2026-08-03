CREATE TABLE IF NOT EXISTS feedback (
    feedback_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    dataset_id      TEXT,
    message         TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id
    ON feedback(user_id);