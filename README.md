# Dasher

Upload a CSV. Get a fully configured, interactive dashboard in minutes.
No column mapping. No chart configuration. No BI expertise required.

Dasher profiles your data automatically, infers what each column means,
and builds and deploys the right charts, then lets you author, edit, and
delete charts in natural language after the fact.

**Stack:** FastAPI · React/Tailwind · PostgreSQL · Metabase · Gemini 3.1 Flash-Lite

> Built with Claude as a development accelerator. Architecture decisions,
> product tradeoffs, and validation are the author's own.

---

## The problem

Getting from raw data to a useful dashboard means manually mapping columns,
choosing chart types, and configuring a BI tool.
Dasher automates this end to end: statistical profiling, LLM-powered semantic
inference, programmatic chart construction and deployment via the Metabase API,
and natural language authoring after the fact. Zero manual configuration at any stage.

---

## Pipeline

1. Upload a CSV
2. Automatic statistical profiling: stats, value counts, correlations, grouped stats
3. Gemini classifies every column: dimensions, measures, dates, flags, identifiers
4. Two-pass dashboard planning: analytical questions first, then charts
5. PostgreSQL-native charts created in Metabase via API, embedded in the UI
6. Natural language authoring: add, edit, or delete charts by describing what you want
7. Natural language insight engine for follow-up questions against live data

---

## Architecture

### Key decisions

**SQL generation, not query abstraction**
Dasher generates raw PostgreSQL directly via the Metabase native query API.
This unlocks the full SQL surface: window functions, CTEs, percentiles,
HAVING, derived metrics, top-N ranking, with no query language intermediary
constraining what can be expressed. All LLM-generated SQL passes through a
validation guard before execution.

**Hallucination risk contained by design**
The LLM generates SQL. Python validates and executes it via persisted field
map lookups. The LLM never touches the database directly. Validation is
deterministic and independently debuggable. Invalid SQL is rejected before
it reaches Metabase.

**Privacy and cost optimisation built into the insight flow**
The natural language insight engine runs in two turns. Turn 1 classifies
whether the question can be answered from cached profile statistics or needs
a live query. In stats mode, no row-level data leaves the system. Both the
privacy boundary and the cost saving are structural, not incidental.

**Dataset-agnostic from day one**
Every dataset gets its own metadata record in Postgres after upload: Metabase
table ID, field IDs, and base types fetched and persisted post-sync. The
pipeline is fully parameterised per dataset with no static config anywhere.

**Upload completes only when Metabase is ready**
After upload, the system validates readiness by running a live query against
Metabase before returning. No fixed sleep intervals. No race conditions. The
frontend only proceeds when the data is genuinely queryable.

**Idempotent dashboard rebuild**
Rebuilding a dashboard deletes the old dashboard and all associated cards
before recreating. Produces a known clean state on every rebuild with no
orphaned cards or state drift.

**Two-stage self-healing chart creation**
Chart creation failures are caught at two levels: Python-level API failures
and Metabase rendering failures on successfully created cards. Both trigger
an automated Gemini-powered heal cycle. Healed charts are flagged with a
before/after diff in the UI. Charts that cannot be healed are dropped cleanly
with a diagnostic summary.

**Natural language dashboard authoring**
After a dashboard is built, charts can be added, edited, or deleted by
typing a description. Each instruction goes through the same Gemini to SQL
and self-healing pipeline as the original build. Card IDs are persisted
back into the dashboard plan so edits survive rehydration.

**Statistical profiling over raw row passing**
The LLM receives a statistical summary of the dataset: means, distributions,
value counts, correlations, rather than raw rows. Token usage is O(columns),
not O(rows). Validated at ~8x lower token cost than naive row-passing with
equivalent semantic inference quality.

### Architecture diagram

*Coming soon*

---

## Decisions and tradeoffs

**Native SQL over query abstraction**
Earlier versions used MBQL, Metabase's internal query language, constructed
programmatically from an LLM-generated intent dict. This was replaced with
direct PostgreSQL generation: simpler architecture, full SQL expressiveness,
and no translation layer between what the LLM wants to express and what gets
executed. The intent dict and MBQL construction layer were removed entirely.

**Privacy-maximalist insight mode**
An architecture where Gemini generates SQL plus a response template with
placeholders, with FastAPI filling values locally, was evaluated and
deliberately deprioritised. It breaks for queries where the insight shape
depends on seeing the data. User capability was weighted over the marginal
privacy gain.

---

## What shipped

- CSV upload with duplicate detection and replace/create-new conflict resolution
- Automatic profiling: stats, value counts, correlations, grouped stats per column
- Gemini semantic inference with confidence scores, cached to Postgres
- Two-pass dashboard planning: questions first, charts second, with post-planning
  validation and deduplication
- PostgreSQL-native chart creation via Metabase API, idempotent rebuild
- Full SQL capability: window functions, CTEs, percentiles, HAVING, derived metrics
- Two-stage self-healing chart creation with Gemini, healed/failed diff in UI
- Public dashboard URL generation and iframe embedding
- Natural language dashboard authoring: add, edit, and delete charts post-build
- Natural language insight engine: two-turn Gemini flow, SQL execution,
  insight history with persistence and delete
- Dataset picker with full rehydration from prior session state
- Validated across five structurally distinct datasets: Mall operations (synthetic),
  Flipkart Diwali sales, IPL deliveries (~260K rows)

---

## Roadmap

**Features**
- [ ] MCP server exposure: Dasher pipeline as an MCP server for Claude Desktop
  and other MCP clients
- [ ] Audience-aware dashboard planning: CXO, engineering, marketing selector
  passed into the plan generation prompt
- [ ] Proactive insight suggestions: autonomous post-build insight generation
  with no user input required
- [ ] Natural language filter: rewrite all dashboard chart SQLs simultaneously
  from a single NL instruction
- [ ] UI overhaul: layout polish, iframe placement, back navigation

**Infrastructure**
- [ ] Async I/O: replace requests + psycopg2 with httpx + asyncpg
- [ ] Cloud deployment and auth


---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload-csv` | Upload CSV, load to Postgres, sync Metabase, persist field map |
| GET | `/datasets` | List uploaded datasets |
| DELETE | `/datasets/{id}` | Delete dataset, Metabase dashboard, and all records |
| GET | `/datasets/{id}/state` | Full pipeline state for frontend rehydration |
| POST | `/infer-dataset-semantics/{id}` | Profile and Gemini semantic inference, cached to Postgres |
| POST | `/generate-dashboard-plan/{id}` | Two-pass LLM dashboard plan with validation |
| POST | `/create-metabase-dashboard/{id}` | Idempotent dashboard and card creation with self-healing |
| POST | `/datasets/{id}/dashboard/charts` | Add a chart via natural language |
| PUT | `/datasets/{id}/dashboard/charts/{card_id}` | Edit a chart via natural language |
| DELETE | `/datasets/{id}/dashboard/charts/{card_id}` | Delete a chart |
| POST | `/datasets/{id}/insights` | Two-turn NL insight generation |
| GET | `/datasets/{id}/insights` | Insight history |
| DELETE | `/datasets/{id}/insights/{insight_id}` | Delete insight entry |

---

## Validation

Chart and insight accuracy tested across 5 datasets including IPL deliveries
at 260K rows. See [validation.md](validation.md) for full results.

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
6. `docker compose up` to start Metabase
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

Production-ready MVP, actively extended. End-to-end functional and validated
across five datasets. New capabilities shipping continuously.