# Dasher

AI-powered dashboarding: upload a CSV, get a fully configured Metabase 
dashboard via LLM-driven semantic inference and automated chart generation.

**Stack:** FastAPI · React/Tailwind · PostgreSQL · Metabase · Gemini 2.5 Flash-Lite

---

## The problem

Manual dashboard creation requires knowing column semantics, choosing chart 
types, and configuring a BI tool — before you've even looked at the data. 
Dasher automates this: it profiles the dataset statistically, uses an LLM to 
infer what each column means and what questions it can answer, then constructs 
and deploys charts programmatically via the Metabase API.

---

## Pipeline

```
CSV upload
    → Statistical profiling (pandas: stats, value counts, correlations, grouped stats)
    → Gemini semantic inference (dimensions, measures, dates, flags, identifiers)
    → Two-pass dashboard planning (analytical questions first, then charts)
    → Metabase chart creation via API
    → Embedded dashboard + natural language insight engine
```

---

## Architecture

### Key decisions

**Dynamic field maps over hardcoded IDs**  
Every dataset gets its own `dataset_metadata` record in Postgres after upload: 
Metabase table ID, field IDs, and base types are fetched and persisted 
post-sync. Static config breaks the moment you load a second dataset; 
the metadata table makes the pipeline fully dataset-agnostic.

**MBQL builder as an architectural boundary**  
The LLM produces an intent dict (aggregation type, breakout column, filter). 
Python constructs the Metabase query language (MBQL) from that intent using 
field map lookups. The LLM never touches the database directly. This boundary 
contains hallucination risk, keeps query construction deterministic, and makes 
failures debuggable — you can inspect the intent and the generated MBQL 
independently.

**Two-turn LLM insight flow**  
Turn 1 classifies whether a natural language question can be answered from 
cached profile statistics or requires a live database query. Turn 2 interprets 
query results into narrative. In stats mode, no row-level data leaves the 
system — a deliberate privacy and cost tradeoff. Query mode is user-initiated 
and documented as the weaker privacy posture.

**Idempotent dashboard rebuild**  
Rebuilding a dashboard deletes the old dashboard and all associated cards 
before recreating. Patching in-place creates orphaned cards and state drift. 
Delete-and-recreate is simpler, auditable, and produces a known clean state 
every time.

**Adaptive Metabase sync polling**  
After upload, the system polls Metabase with a live validation query rather 
than sleeping for a fixed interval. The upload endpoint only returns when 
Metabase can actually execute a query against the new table — eliminating 
intermittent card creation failures caused by race conditions.

---

### System overview

```
┌─────────────────────────────────────────────────┐
│                  React Frontend                  │
│  Upload → Semantics → Plan → Dashboard/Insights  │
└────────────────────┬────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────┐
│                  FastAPI Backend                  │
│                                                  │
│  routes/          services/                      │
│  uploadsRoute  →  csvLoader    → PostgreSQL      │
│  semanticsRoute→  llmClient    → Gemini API      │
│  dashboardRoute→  dashboardPlanner               │
│  metabaseRoute →  metabaseClient → Metabase API  │
│  insightsRoute →  insightGenerator               │
└──────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              PostgreSQL (local)                  │
│  dataset_metadata · dataset_semantics            │
│  dashboard_plans  · dataset_insights             │
└──────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│           Metabase (Docker)                      │
│  Charts created and managed via REST API         │
│  Public embed URL generated per dashboard        │
└──────────────────────────────────────────────────┘
```

---

### Folder structure

```
dasher/
  backend/
    app/
      routes/       # FastAPI route handlers (*Route.py convention)
      services/     # Business logic: profiler, llmClient, metabaseClient,
      │             # csvLoader, dashboardPlanner, insightGenerator
      schemas/      # Pydantic v2 request/response models
      config.py     # Centralised settings via pydantic-settings
      main.py       # App entrypoint
    db/
      migrations/   # SQL migration files (001–004, run in order)
  frontend/
    src/
      hooks/        # useDasher.js — all pipeline state
      lib/          # api.js — fetch wrappers per endpoint
      components/   # Step components, InsightsPanel
  dataset/          # Sample datasets for local testing
```

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload-csv` | Upload CSV, load to Postgres, sync Metabase, persist field map |
| GET | `/datasets` | List uploaded datasets |
| DELETE | `/datasets/{id}` | Delete dataset, Metabase dashboard, and all records |
| GET | `/datasets/{id}/state` | Full pipeline state for frontend rehydration |
| POST | `/infer-dataset-semantics/{id}` | Profile + Gemini semantic inference, cached to Postgres |
| POST | `/generate-dashboard-plan/{id}` | Two-pass LLM dashboard plan with post-planning validation |
| POST | `/create-metabase-dashboard/{id}` | Idempotent dashboard + card creation via Metabase API |
| POST | `/datasets/{id}/insights` | Two-turn NL insight generation |
| GET | `/datasets/{id}/insights` | Insight history |
| DELETE | `/datasets/{id}/insights/{insight_id}` | Delete insight entry |

---

## Decisions and tradeoffs

These items were explicitly evaluated and parked — not overlooked.

**Heterogeneous column aggregation**  
Columns like `result_margin` in cricket data mix runs and wickets in the same 
field. Aggregating without filtering by a sibling categorical is semantically 
meaningless. The right fix requires a preprocessing layer to detect and split 
these columns — added 3x complexity for marginal gain on otherwise clean CSVs. 
Schema fields and prompt updates exist; LLM prompt compliance was the 
blocking issue.

**Privacy-maximalist insight mode**  
Evaluated an architecture where Gemini generates MBQL plus a response template 
with placeholders, and FastAPI fills values locally — so no query results ever 
reach the LLM. Parked because it breaks for analytical queries where the 
insight shape depends on the data (e.g. "which team wins most often" requires 
seeing the top result to structure the response).

**ETL / preprocessing layer**  
Decided to assume reasonably clean CSVs for MVP scope. Unit-suffix columns 
(e.g. "58.16 bhp") are dataset-specific rather than generalizable enough to 
justify a preprocessing layer at this stage.

---

## Validation

Tested across three structurally distinct datasets:

- **Mall operations** — original development dataset
- **Diwali sales** — Indian retail, comma-formatted numbers, mixed categoricals
- **IPL deliveries** — ~260K rows, cricket domain, binary flag measures, 
  heterogeneous numeric columns

Full validation pass (chart accuracy rate, NL insight accuracy across 10 
representative questions) is a tracked roadmap item — see below.

---

## Roadmap

**Features**
- [ ] Natural language chart manipulation — select a chart, type an instruction, 
  Gemini returns an updated spec, PUT to Metabase card API. Dependency: card IDs 
  need to be persisted post-creation.
- [ ] Audience-aware dashboard planning — optional audience selector (CXO, 
  engineering, marketing) passed into plan generation prompt alongside semantics
- [ ] HAVING clause support — post-aggregation filtering in MBQL builder
- [ ] Pipeline step restart — re-run semantics or plan without re-uploading
- [ ] Heterogeneous column support — per-value chart generation for columns with 
  mixed units (schema and prompt groundwork exists)

**Quality and validation**
- [ ] Formal validation pass: chart accuracy rate across all three datasets, 
  NL insight accuracy (10 questions, IPL dataset), time-to-dashboard vs manual baseline
- [ ] Remove debug print statements from backend
- [ ] Postman collection for API testing

**Infrastructure**
- [ ] UI overhaul — layout polish, iframe placement, back navigation
- [ ] Cloud deployment with scalability considerations
- [ ] Auth and multi-tenancy (out of scope for current phase)

---

## Local setup

### Prerequisites
- Python 3.11+
- Node.js + npm
- Docker Desktop
- PostgreSQL on port 5432
- Google AI Studio API key

### Steps

1. Clone the repo
2. Create and activate a Python virtual environment
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in values
5. Run DB migrations in order: `db/migrations/001` through `004`
6. `docker compose up` — starts Metabase
7. `uvicorn app.main:app --reload` from `backend/`
8. `npm run dev` from `frontend/`

### Environment variables

| Variable | Description |
|----------|-------------|
| `UPLOAD_DIR` | Path to CSV upload directory |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `DATABASE_URL` | Postgres connection string |
| `METABASE_URL` | Metabase base URL (default: http://localhost:3000) |
| `METABASE_USERNAME` | Metabase admin username |
| `METABASE_PASSWORD` | Metabase admin password |
| `METABASE_DB_NAME` | Name of the database as it appears in Metabase |

---

## Status

MVP complete. Pipeline is end-to-end functional. Active development continues 
on the items above.