# Dasher

An AI-enabled dashboarding platform that transforms raw business datasets 
into structured, insight-ready dashboards — with minimal manual configuration.

Upload a dataset, let AI infer its structure, and get a dashboard plan ready 
for visualisation in Metabase.

---

## What it does

Traditional BI setup requires manual column mapping, chart configuration, 
and domain knowledge to get from raw data to a useful dashboard. Dasher 
removes that friction.

The core flow:

1. Upload a CSV dataset
2. System profiles the data automatically
3. AI infers semantic meaning of every column (dimensions, measures, flags, dates)
4. A dashboard plan is generated from the inferred semantics
5. Charts are created in Metabase via API

---

## Architecture

### Stack

| Layer | Technology |
|---|---|
| API / Orchestration | FastAPI (Python) |
| AI Inference | Google Gemini 2.5 Flash-Lite |
| Dashboard / BI | Metabase (Docker) |
| Database | PostgreSQL (local) |
| Container Runtime | Docker Desktop |

### Key design decisions

**AI for semantic inference, not rules**
Rather than building domain-specific column mapping rules, Dasher uses an 
LLM to infer column semantics from profiled data. Output is constrained to 
strict JSON with confidence scores, keeping the AI layer predictable and 
testable.

**Metabase as the BI layer**
Dashboard rendering is not built from scratch. Metabase handles all 
visualisation. FastAPI orchestrates the flow and drives Metabase via its API.

**Persisted inference**
Semantic inference results are stored in Postgres after the first call. 
Subsequent dashboard plan generation reads from the database, avoiding 
redundant LLM calls.

**Separation of inference and planning**
Semantics inference and dashboard plan generation are separate endpoints. 
This enables users to review, modify, and regenerate individual charts 
without re-running the full inference pipeline.

### Folder structure
```
dasher/
  backend/
    app/
      routes/         # FastAPI route handlers
      services/       # Business logic (profiler, LLM client)
      schemas/        # Pydantic request/response models
      config.py       # Centralised settings via pydantic-settings
      main.py         # App entrypoint
    db/
      migrations/     # SQL migration files (run in order)
      README.md       # DB setup instructions
  dataset/            # Sample datasets for local development
  .env                # Local environment variables (not committed)
```

### Networking note
Metabase runs in Docker. PostgreSQL runs on the Windows host. 
Connection from Metabase to Postgres uses `host.docker.internal` 
instead of `localhost`.

---

## API endpoints

### Upload

`POST /upload-csv`
Accepts a CSV file. Returns a `dataset_id` and file metadata.

### Datasets

`GET /datasets`
Lists all uploaded datasets.

### Profile

`GET /datasets/{dataset_id}/profile`
Returns a full column profile: row count, column count, inferred types, 
sample values, null counts, distinct counts, candidate date/numeric/categorical columns.

### Semantic Inference

`POST /infer-dataset-semantics/{dataset_id}`
Profiles the dataset and calls Gemini to infer semantic roles for every column.
Returns structured JSON with date columns, dimensions, measures, flags, 
identifiers, unknowns, dataset grain, and confidence scores.
Result is persisted to Postgres. Subsequent calls return cached result.

Body (optional):
```json
{
  "business_hint": "Mall operations"
}
```

### Dashboard Plan (coming soon)

`POST /generate-dashboard-plan/{dataset_id}`
Reads persisted semantics and generates a recommended chart plan.
Returns chart types, axis mappings, filter suggestions, and reasoning.

---

## Local setup

### Prerequisites
- Python 3.11+
- Docker Desktop
- PostgreSQL running locally on port 5432
- Google AI Studio API key

### Steps

1. Clone the repo
2. Create and activate a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in values
5. Run DB migrations: see `backend/db/README.md`
6. Start Metabase: `docker compose up`
7. Start API: `uvicorn app.main:app --reload` from `backend/`

### Environment variables

| Variable | Description |
|---|---|
| `UPLOAD_DIR` | Path to CSV upload directory |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `DATABASE_URL` | Postgres connection string |

---

## Status

This is an MVP built for demo and pitch purposes. 
Production hardening, auth, and multi-tenancy are out of scope for this phase.

---

## Roadmap

- [x] CSV upload and profiling
- [x] AI semantic inference with structured JSON output
- [ ] Postgres persistence for inference results
- [ ] Dashboard plan generation
- [ ] Metabase chart auto-creation via API
- [ ] User-facing chart modification and regeneration
- [ ] Natural language insight generation