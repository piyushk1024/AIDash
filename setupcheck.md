New machine setup checklist
Prerequisites to install manually:

Python 3.11+
Docker Desktop
PostgreSQL 18
pgAdmin (optional but recommended)
Git

Steps in order:

Clone the repo
Create and activate a virtual environment
Run pip install -r requirements.txt
Recreate .env from .env.example with your real values
Start PostgreSQL service
Create the database: CREATE DATABASE MallOpsDB; in pgAdmin or psql
Run migrations: psql -U postgres -d MallOpsDB -f backend/db/migrations/001_initial_schema.sql
Pull the Metabase Docker image and start it: docker compose up (or whatever your Docker setup is)
Configure Metabase fresh: connect to Postgres using host.docker.internal, recreate the database connection
Note the new Metabase database ID and table ID since they will differ from your current machine
Update DATABASE_ID and TABLE_ID and FIELD_MAP in metabaseClient.py to match the new Metabase IDs
Re-upload your CSV and re-run the full pipeline to regenerate semantics and dashboard plan
Start the API: uvicorn app.main:app --reload from backend/

The fragile parts to watch:
The Metabase internal IDs (database ID, table ID, field IDs) will be different on every fresh Metabase instance. Step 11 is the one most likely to trip you up. Keep the field ID lookup process documented so you can redo it quickly.