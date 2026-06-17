# Dasher

Upload a CSV. Get a fully configured, interactive, authenticated dashboard in minutes.
No column mapping. No chart configuration. No BI expertise required.

Dasher profiles your data automatically, infers what each column means, builds and
deploys the right charts, and lets you author, edit, and delete charts in natural
language after the fact. Dashboards are shareable via a public URL with one click.

**Stack:** FastAPI · React/Tailwind · PostgreSQL · Metabase · LiteLLM · Gemini 3.1 Flash-Lite · asyncpg · httpx · PyJWT

> Built with Claude as a development accelerator. Architecture decisions,
> product tradeoffs, and validation are the author's own.

---

## The problem

Getting from raw data to a useful dashboard means manually mapping columns,
choosing chart types, and configuring a BI tool.
Dasher automates this end to end: statistical profiling, LLM-powered semantic
inference, programmatic chart construction and deployment via the Metabase API,
natural language authoring after the fact, and one-click public sharing.
Zero manual configuration at any stage.

---

## Pipeline

1. Upload a CSV
2. Automatic statistical profiling: stats, value counts, correlations, grouped stats
3. LLM classifies every column: dimensions, measures, dates, flags, identifiers
4. Two-pass dashboard planning: analytical questions first, then charts
5. PostgreSQL-native charts created in Metabase via API, embedded in the UI
6. Natural language authoring: add, edit, or delete charts by describing what you want
7. Natural language insight engine for follow-up questions against live data
8. Publish to a public share URL, or keep private

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

**LLM-agnostic by design**
All LLM calls are routed through a single LiteLLM wrapper. Switching from
Gemini to GPT-4o or Claude is a one-line config change with no downstream
code changes anywhere in the pipeline. Provider, model, and API key are
all externalised to environment variables.

**Statistical profiling over raw row passing**
The LLM receives a statistical summary of the dataset: means, distributions,
value counts, and correlations; not raw rows. Token usage is O(columns),
not O(rows). Validated across multiple datasets:

| Dataset | Rows | Token ratio (Dasher vs naive) | Cost ratio |
|---|---|---|---|
| IPL deliveries | 260,920 | 1x vs 4.3x (at 1k rows sampled) | 1x vs 3.5x |
| API error logs | 220,000 | 1x vs 9.9x (at 1k rows sampled) | 1x vs 8.0x |

The efficiency advantage is structural and scales with row count. At full dataset
scale, naive row-passing is impractical. Dashboard cost can be as low as $0.002.

**Privacy and cost optimisation built into the insight flow**
The natural language insight engine runs in two turns. Turn 1 classifies whether
the question can be answered from cached profile statistics or requires a live
query. In stats mode, no row-level data leaves the system. Both the privacy
boundary and the cost saving are structural, not incidental.

**Auth and ownership built into every layer**
JWT tokens carry user identity on every request. Dataset ownership is enforced
at the database layer via a dedicated `get_dataset_owner` helper, not at the
route layer. Every write route checks ownership after a 404 guard and returns
403 on mismatch. The dataset list silently filters to the authenticated user.
Metabase is treated as a rendering layer only. All access control lives in
Dasher's auth stack.

**Public sharing without exposing internals**
Published dashboards are served via an open `/datasets/{id}/public` endpoint
that returns only the Metabase public embed URL. The Metabase dashboard integer
ID is never exposed. The share URL is a Dasher URL, not a Metabase URL.
Publishing is a deliberate owner action via a toggle; dashboards are private
by default.

**Fully async I/O stack**
All database access runs through an asyncpg connection pool. All HTTP calls
to Metabase run through an httpx.AsyncClient. Both are initialised in the
FastAPI lifespan hook on `app.state` and injected via dependency injection.
The event loop is never blocked. Validated under concurrent load across
multiple simultaneous dataset pipelines.

**Dataset-agnostic from day one**
Every dataset gets its own metadata record in Postgres after upload: Metabase
table ID, field IDs, and base types fetched and persisted post-sync. The
pipeline is fully parameterised per dataset with no static config anywhere.

**Upload completes only when Metabase is ready**
After upload, the system validates readiness by polling Metabase until the
table is queryable before returning. No fixed sleep intervals. No race
conditions. The frontend only proceeds when the data is genuinely ready.

**Idempotent dashboard rebuild**
Rebuilding a dashboard deletes the old dashboard and all associated cards
before recreating. Produces a known clean state on every rebuild with no
orphaned cards or state drift.

**Two-stage self-healing chart creation**
Chart creation failures are caught at two levels: Python-level API failures
and Metabase rendering failures on successfully created cards. Both trigger
an automated LLM-powered heal cycle. Healed charts are flagged with a
before/after diff in the UI. Charts that cannot be healed are dropped cleanly.

**Natural language dashboard authoring**
After a dashboard is built, charts can be added, edited, or deleted by
typing a description. Each instruction goes through the same LLM-to-SQL
and self-healing pipeline as the original build. Card IDs are persisted
back into the dashboard plan so edits survive rehydration.

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

**Metabase as a rendering layer, not an auth boundary**
Metabase's own user and permission system is bypassed deliberately. A single
service account authenticates with Metabase. All user-level access control
runs in Dasher's JWT layer. This simplifies the stack and keeps auth logic
in one place rather than split across two systems.

**Privacy-maximalist insight mode**
An architecture where the LLM generates SQL plus a response template with
placeholders, with FastAPI filling values locally, was evaluated and
deliberately deprioritised. It breaks for queries where the insight shape
depends on seeing the data. User capability was weighted over the marginal
privacy gain.

**LiteLLM over direct SDK calls**
LLM calls were originally made directly via the google-genai SDK. These were
consolidated behind a single LiteLLM wrapper, making the provider swappable
via config with no downstream code changes. The abstraction cost was one
small service file. The flexibility gain is permanent.

---

## What shipped

- JWT authentication: register, login, token-based session management
- Per-user dataset ownership enforced at database layer, 403 on mismatch
- CSV upload with duplicate detection and replace/create-new conflict resolution
- Automatic profiling: stats, value counts, correlations, grouped stats per column
- LLM semantic inference with confidence scores, cached to Postgres
- Two-pass dashboard planning: questions first, charts second, with post-planning
  validation and deduplication
- PostgreSQL-native chart creation via Metabase API, idempotent rebuild
- Full SQL capability: window functions, CTEs, percentiles, HAVING, derived metrics
- Two-stage self-healing chart creation with LLM, healed/failed diff in UI
- Public dashboard publishing: owner-controlled toggle, open share endpoint,
  Dasher-native share URL
- Natural language dashboard authoring: add, edit, and delete charts post-build
- Natural language insight engine: two-turn LLM flow, SQL execution,
  insight history with persistence and delete
- Fully async I/O: asyncpg connection pool, httpx.AsyncClient, lifespan-managed
- Dataset picker with full rehydration from prior session state
- LLM-agnostic via LiteLLM: swap provider with a single config change
- Validated across five structurally distinct datasets: Mall operations,
  Flipkart Diwali sales, IPL deliveries (~260K rows), API error logs (~220K rows),
  Cars and employee datasets

---

## Roadmap

**Done**
- [x] Async I/O: asyncpg + httpx, lifespan-managed pool and client
- [x] JWT auth and per-user dataset ownership
- [x] Public share and publish
- [x] Natural language dashboard authoring
- [x] Natural language insight engine
- [x] LiteLLM abstraction

**Next**
- [ ] UI overhaul: sidebar pipeline layout, per-card iframe grid, component decomposition
- [ ] Cloud deployment: Railway, S3/R2 for CSV storage, cold-start seeding
- [ ] Security hardening: server-side Metabase iframe proxy, permissions lockdown,
  endpoint audit

**Features**
- [ ] MCP server exposure: Dasher pipeline as an MCP server for Claude Desktop
  and other MCP clients
- [ ] Audience-aware dashboard planning: CXO, engineering, marketing selector
  passed into the plan generation prompt
- [ ] Proactive insight suggestions: autonomous post-build insight generation
- [ ] Natural language filter: rewrite all dashboard chart SQLs from a single instruction

---

## API reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | Open | Create account, returns user\_id and role |
| POST | `/auth/login` | Open | Returns JWT access\_token |
| POST | `/upload-csv` | Required | Upload CSV, load to Postgres, sync Metabase |
| GET | `/datasets` | Required | List datasets for authenticated user |
| DELETE | `/datasets/{id}` | Required | Delete dataset, dashboard, and all records |
| GET | `/datasets/{id}/state` | Required | Full pipeline state for rehydration |
| GET | `/datasets/{id}/public` | Open | Public embed URL if published, 404 otherwise |
| POST | `/datasets/{id}/publish` | Required | Toggle published state |
| POST | `/infer-dataset-semantics/{id}` | Required | LLM semantic inference, cached |
| POST | `/generate-dashboard-plan/{id}` | Required | Two-pass LLM dashboard plan |
| POST | `/create-metabase-dashboard/{id}` | Required | Idempotent dashboard creation with self-healing |
| POST | `/datasets/{id}/dashboard/charts` | Required | Add chart via natural language |
| PUT | `/datasets/{id}/dashboard/charts/{card_id}` | Required | Edit chart via natural language |
| DELETE | `/datasets/{id}/dashboard/charts/{card_id}` | Required | Delete chart |
| POST | `/datasets/{id}/insights` | Required | Two-turn NL insight generation |
| GET | `/datasets/{id}/insights` | Required | Insight history |
| DELETE | `/datasets/{id}/insights/{insight_id}` | Required | Delete insight entry |

---

## Validation

Chart and insight accuracy tested across 5 datasets including IPL deliveries
at 260K rows. 14/17 chart accuracy across 3 datasets. Cost efficiency validated
via `costValidation.py` across 3 datasets at varying scales.

---

## Local setup

### Prerequisites
- Python 3.11+
- Node.js + npm
- Docker Desktop
- PostgreSQL on port 5432
- API key for your LLM provider (Gemini, OpenAI, or Anthropic)

### Steps

1. Clone the repo
2. Create and activate a Python virtual environment
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in values
5. Run DB migrations in order: `db/migrations/001` through `005`
6. `docker compose up` to start Metabase
7. `uvicorn app.main:app --reload` from `backend/`
8. `npm run dev` from `frontend/`

### Environment variables

| Variable | Description |
|----------|-------------|
| `UPLOAD_DIR` | Path to CSV upload directory |
| `LLM_API_KEY` | API key for your chosen LLM provider |
| `LLM_MODEL` | LiteLLM model string, e.g. `gemini/gemini-3.1-flash-lite`, `openai/gpt-4o-mini` |
| `DATABASE_URL` | Postgres connection string |
| `METABASE_URL` | Metabase base URL (default: http://localhost:3000) |
| `METABASE_USERNAME` | Metabase admin username |
| `METABASE_PASSWORD` | Metabase admin password |
| `METABASE_DB_NAME` | Name of the database as it appears in Metabase |
| `JWT_SECRET` | Secret key for JWT signing |
| `JWT_ALGORITHM` | JWT algorithm (default: HS256) |
| `JWT_EXPIRY_HOURS` | Token expiry in hours (default: 24) |
| `DB_POOL_MIN` | asyncpg pool minimum connections (default: 2) |
| `DB_POOL_MAX` | asyncpg pool maximum connections (default: 10) |

---

## Status

Production-ready MVP, actively extended. End-to-end functional and validated
across five datasets. Auth, ownership, async I/O, and public sharing all shipped.
New capabilities shipping continuously.
