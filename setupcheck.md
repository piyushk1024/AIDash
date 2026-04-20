New Machine Setup Checklist
Prerequisites to install manually:

Python 3.11+
Docker Desktop
PostgreSQL 18
pgAdmin 4 (optional but recommended)
Git
Postman (optional but recommended for API testing)

Steps in order:

Clone the repo
Create and activate a virtual environment
Run pip install -r requirements.txt
Recreate .env from .env.example with your real values — make sure METABASE_DB_NAME exactly matches the database name you will set in Metabase (step 9)
Start PostgreSQL service
Install node packages: npm install
Create the database in pgAdmin or psql: CREATE DATABASE MallOpsDB;
Run all three migrations in order:

psql -U postgres -d MallOpsDB -f backend/db/migrations/001_initial_schema.sql
psql -U postgres -d MallOpsDB -f backend/db/migrations/002_dataset_metadata.sql
psql -U postgres -d MallOpsDB -f backend/db/migrations/003_add_dashboard_id.sql

Start Metabase: docker compose up from the project root
Configure Metabase fresh: connect it to Postgres using host.docker.internal, name the database connection to match your METABASE_DB_NAME value exactly
Enable public sharing in Metabase: Admin → Settings → Public Sharing → On
Start the API: uvicorn app.main:app --reload from backend/
Start the frontend: npm run dev from the frontend directory
Re-upload your CSV and re-run the full pipeline — all Metabase IDs are fetched dynamically, nothing needs to be hardcoded or manually noted

The fragile parts to watch:

METABASE_DB_NAME in .env must exactly match the name you give the database connection in Metabase during step 9 — this is the one value that bridges the two systems
psql may not be in PATH on Windows — use pgAdmin's Query Tool to run migrations instead
Metabase takes a minute or two to start up before it's accessible at localhost:3000
