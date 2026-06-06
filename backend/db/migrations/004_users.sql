CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    username        TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'editor',
    created_at      TIMESTAMP DEFAULT NOW()
);