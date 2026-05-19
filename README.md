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
Dasher automates this: it profiles the dataset statistically, uses an LLM to
infer what each column means and what questions it can answer, then constructs
and deploys charts programmatically via the Metabase API, and keeps the
dashboard editable via natural language after creation.

---

## Pipeline

1. Upload a CSV
2. Automatic statistical profiling (stats, value counts, correlations, grouped stats)
3. Gemini classifies every column: dimensions, measures, dates, flags, identifiers
4. Two-pass dashboard planning: analytical questions first, then charts
5. Charts created in Metabase via API, dashboard embedded in the UI
6. Natural language authoring: add, edit, or delete charts by describing what you want
7. Natural language insight engine for follow-up questions against live data

---

## Architecture

### Key decisions

**Hallucination risk contained by design**
The LLM produces an intent dict describing what to query. Python constructs
the Metabase query language (MBQL) from that intent using persisted field map
lookups. The LLM never touches the database directly. Query construction is
deterministic and independently debuggable.

**Privacy and cost optimisation built into the insight flow**
The natural language insight engine runs in two turns. Turn 1 classifies
whether the question can be answered from cached profile statistics or needs
a live query. In stats mode, no row-level data leaves the system. Query mode
is user-initiated. Both the privacy boundary and the cost saving are
structural, not incidental.

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
before/after diff in the UI. Charts that can't be healed are dropped cleanly
with a diagnostic summary.

**Natural language dashboard authoring**
After a dashboard is built, charts can be added, edited, or deleted by
typing a description. Each instruction goes through the same Gemini →
MBQL and self-healing pipeline as the original build. Card IDs are persisted
back into the dashboard plan so edits survive rehydration.

### Architecture diagram

*Coming soon*

---

## Decisions and tradeoffs

**Heterogeneous column aggregation**
Some columns mix units in a single field (e.g. runs and wickets in cricket
data). Aggregating these without filtering by a sibling categorical is
semantically meaningless. Schema fields, prompt handling, and MBQL filter
construction are built; this was scoped out of the initial release due to
LLM prompt compliance being insufficiently reliable for production use.

**Privacy-maximalist insight mode**
An architecture where Gemini generates MBQL plus a response template with
placeholders, with FastAPI filling values locally, was evaluated and
deliberately deprioritised. It breaks for queries where the insight shape
depends on seeing the data. User capability was weighted over the marginal
privacy gain.

**Statistical profiling over raw row passing**
The LLM receives a statistical summary of the dataset (means, distributions,
value counts, correlations) rather than raw rows. Token usage is O(columns),
not O(rows). Validated at ~8x lower token cost than naive row-passing with
equivalent semantic inference quality.

---

## What shipped

- CSV upload with duplicate detection and replace/create-new conflict resolution
- Automatic profiling: stats, value counts, correlations, grouped stats per column
- Gemini semantic inference with confidence scores, cached to Postgres
- Two-pass dashboard planning: questions first, charts second, with post-planning
  validation and deduplication
- Metabase chart auto-creation via API, idempotent rebuild
- Two-stage self-healing chart creation with Gemini, healed/failed diff in UI
- Public dashboard URL generation and iframe embedding
- Natural language dashboard authoring: add, edit, and delete charts post-build
- Natural language insight engine: two-turn Gemini flow, MBQL builder,
  insight history with persistence and delete
- Dataset picker with full rehydration from prior session state
- Validated across three structurally distinct datasets: mall operations,
  Diwali sales (Indian retail, comma-formatted numbers), IPL deliveries (~260K rows)

---

## Roadmap

**Features**
- [ ] Healing persistence: persist healed/failed card diffs to Postgres, survive rehydration
- [ ] Audience-aware dashboard planning: CXO, engineering, marketing selector
  passed into the plan generation prompt
- [ ] HAVING clause support for post-aggregation filtering in MBQL builder
- [ ] Heterogeneous column support: per-value chart generation for mixed-unit columns

**Infrastructure**
- [ ] MCP server exposure: Dasher pipeline as an MCP server for Claude Desktop
  and other MCP clients
- [ ] Cloud deployment and auth
- [ ] UI overhaul: layout polish, iframe placement, back navigation
- [ ] Async I/O: replace requests + psycopg2 with httpx + asyncpg for concurrent load handling

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

Chart and insight accuracy tested across 3 datasets. See [validation.md](validation.md) for full results.

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

MVP complete and actively extended. Pipeline is end-to-end functional,
validated across multiple datasets, and shipping new capabilities.
