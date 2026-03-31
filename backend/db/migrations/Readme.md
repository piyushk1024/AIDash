## Database Setup

1. Create a Postgres database named `dasher` (or your preferred name)
2. Run migrations in order:

psql -U postgres -d dasher -f migrations/001_initial_schema.sql

## Adding future migrations
Name them sequentially: 002_..., 003_...
Never edit existing migration files.