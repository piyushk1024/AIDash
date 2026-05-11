# Dasher

Upload a CSV. Get a fully configured, interactive dashboard in minutes.
No column mapping. No chart configuration. No BI expertise required.

Dasher profiles your data automatically, infers what each column means,
and builds and deploys the right charts for it without any manual setup.

**Stack:** FastAPI · React/Tailwind · PostgreSQL · Metabase · Gemini 3.1 Flash-Lite

> Built with Claude as a development accelerator. Architecture decisions,
> product tradeoffs, and validation are the author's own.

---

## The problem

Getting from raw data to a useful dashboard means manually mapping columns,
choosing chart types, and configuring a BI tool. 
Dasher automates this: it profiles the dataset statistically, uses an LLM to
infer what each column means and what questions it can answer, then constructs
and deploys charts programmatically via the Metabase API.

---

## Pipeline

1. Upload a CSV
2. Automatic statistical profiling (stats, value counts, correlations, grouped stats)
3. Gemini classifies every column: dimensions, measures, dates, flags, identifiers
4. Two-pass dashboard planning: analytical questions first, then charts
5. Charts created in Metabase via API, dashboard embedded in the UI
6. Natural language insight engine for follow-up questions

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
before recreating. This avoids orphaned cards and state drift, and produces
a known clean state on every rebuild.

### Architecture diagram

*Coming soon*

---

## Decisions and tradeoffs

**Heterogeneous column aggregation**
Some columns mix units in a single field (e.g. runs and wickets in cricket
data). Aggregating these without filtering by a sibling categorical is
semantically meaningless. This is a solvable problem requiring a preprocessing
layer. Schema fields and prompt updates already exist in the codebase;
this was scoped out of MVP to avoid 3x complexity increase for marginal gain
on clean datasets.

**Privacy-maximalist insight mode**
An architecture where Gemini generates MBQL plus a response template with
placeholders, with FastAPI filling values locally, was evaluated and
deliberately deprioritised. It breaks for queries where the insight shape
depends on seeing the data. User capability was weighted over the marginal
privacy gain.

**ETL layer**
Assumed reasonably clean CSVs for MVP scope. Unit-suffix columns and
dataset-specific formatting are too varied to generalise at this stage.
CSV hardening (NA variants, comma-formatted numbers, blank rows, summary
row detection) is built in.

---

## What shipped

- CSV upload with duplicate detection and replace/create-new conflict resolution
- Automatic profiling: stats, value counts, correlations, grouped stats per column
- Gemini semantic inference with confidence scores, cached to Postgres
- Two-pass dashboard planning: questions first, charts second, with post-planning
  validation and deduplication
- Metabase chart auto-creation via API, idempotent rebuild
- Public dashboard URL generation and iframe embedding
- Natural language insight engine: two-turn Gemini flow, MBQL builder,
  insight history with persistence and delete
- Dataset picker with rehydration from prior session state
- Validated across three structurally distinct datasets: mall operations,
  Diwali sales (Indian retail, comma-formatted numbers), IPL deliveries (~260K rows)

---

## Roadmap

**Features**
- [ ] Natural language chart manipulation: select a chart, type an instruction,
  Gemini returns an updated spec, PUT to Metabase card API
- [ ] Audience-aware dashboard planning: CXO, engineering, marketing selector
  passed into the plan generation prompt
- [ ] HAVING clause support for post-aggregation filtering in MBQL builder
- [ ] Pipeline step restart: re-run semantics or plan without re-uploading
- [ ] Heterogeneous column support: per-value chart generation for mixed-unit columns

**Quality**
- [x] Formal validation pass: 14/17 chart accuracy across 3 datasets,
  NL insight accuracy validated, cost efficiency confirmed O(columns)
  time-to-dashboard vs manual baseline
- [ ] Postman collection for API testing
- [ ] Remove debug print statements from backend

**Infrastructure**
- [ ] UI overhaul: layout polish, iframe placement, back navigation
- [ ] Cloud deployment
- [ ] Auth and multi-tenancy

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
| POST | `/create-metabase-dashboard/{id}` | Idempotent dashboard and card creation |
| POST | `/datasets/{id}/insights` | Two-turn NL insight generation |
| GET | `/datasets/{id}/insights` | Insight history |
| DELETE | `/datasets/{id}/insights/{insight_id}` | Delete insight entry |

---

## Validation

Chart and insight accuracy tested across 3 datasets. See [validation.md](validation.md) for full results.

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

MVP complete. Pipeline is end-to-end functional and validated.
Active development continues on the items above.