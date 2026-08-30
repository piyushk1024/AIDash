CREATE TABLE geo_reference (
    id SERIAL PRIMARY KEY,
    granularity TEXT NOT NULL CHECK (granularity IN ('city', 'state')),
    name TEXT NOT NULL,              -- normalized lowercase, for matching
    display_name TEXT NOT NULL,      -- proper case, for rendering
    state TEXT,                      -- populated for city rows, NULL for state rows
    country TEXT NOT NULL,           -- 'IN' or 'US'
    lat NUMERIC NOT NULL,
    lon NUMERIC NOT NULL,
    aliases TEXT[],                  -- nullable, alt spellings (bombay/mumbai)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (granularity, country, name)
);

CREATE INDEX idx_geo_reference_lookup ON geo_reference (granularity, country, name);