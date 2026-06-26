# Dasher

Upload a CSV. Get a deployed, interactive dashboard in minutes. No column mapping, no chart config, no BI expertise required.

**Stack:** FastAPI · React/Tailwind · PostgreSQL · Metabase · LiteLLM · Gemini 2.5 Flash-Lite · asyncpg · httpx · PyJWT

> Built with Claude as a development accelerator. Architecture decisions, product tradeoffs, and validation are the author's own.

---

Dasher is an AI-enabled dashboarding tool and portfolio project built to demonstrate
agentic AI patterns, production-grade API design, and end-to-end system thinking.
It runs two build modes: a sequential pipeline (profile → semantics → plan → build)
and an agentic mode where an LLM orchestrates the same pipeline via native
function-calling with no LangChain dependency. Both modes produce a fully deployed,
embedded, shareable Metabase dashboard from a raw CSV upload.

## The problem

Getting from raw data to a useful dashboard requires manually mapping columns,
choosing chart types, writing queries, and configuring a BI tool. It demands
both domain knowledge and BI expertise. Most people skip it.
Dasher automates the full chain: statistical profiling, LLM semantic inference,
dashboard planning, and programmatic chart deployment via the Metabase API.
The only input required is a CSV and an optional one-line description of the data.

---

## What it does

1. Upload a CSV, profiled automatically (stats, value counts, correlations)
2. LLM classifies every column: dimensions, measures, dates, flags, identifiers
3. Two-pass dashboard planning: analytical questions first, then charts
4. PostgreSQL-native charts created in Metabase via API, embedded in the UI
5. Natural language authoring: add, edit, or delete charts post-build
6. Natural language insight engine against live data
7. One-click public sharing

---

## Engineering highlights

**O(columns) not O(rows) LLM cost**
The LLM receives a statistical profile, not raw rows. Token usage scales with schema width, not dataset size. Validated across multiple datasets:

| Dataset | Rows | Token ratio vs naive | Cost ratio |
|---|---|---|---|
| IPL deliveries | 260,920 | 1x vs 4.3x | 1x vs 3.5x |
| API error logs | 220,000 | 1x vs 9.9x | 1x vs 8.0x |

Dashboard cost as low as $0.002 regardless of row count.

**Native SQL generation**
Raw PostgreSQL generated directly via Metabase's native query API: window functions, CTEs, percentiles, HAVING, derived metrics, top-N. No query abstraction layer constraining expressiveness. All LLM-generated SQL passes an AST-based validation guard before execution.

**Agentic mode with native function-calling**
An LLM agent orchestrates the full pipeline via native Gemini function-calling, no LangChain or LangGraph. Tools: `inspect_data`, `build_and_add_chart`, `finish`. Agent goal is pre-populated from the business context set at upload time; editable before launch.

**Two-stage self-healing**
Chart failures caught at two levels: Python API failures and Metabase rendering failures. Both trigger an automated LLM-powered heal cycle. Healed charts flagged in UI with before/after diff.

**Semantics staleness cascade**
Re-running semantic inference with a changed hint marks the downstream plan stale via `stale` + `generation_counter` on `dashboard_plans`. The `force` flag bypasses the LLM cache without triggering staleness. Hint change and forced refresh are handled as distinct cases.

**Profile caching removes CSV dependency**
Statistical profile persisted to `dataset_metadata.profile_json` on first run. All downstream stages read from cache. Foundational step toward discarding the CSV post-upload. The file is only needed once.

**Content-based upload deduplication**
SHA-256 checksum stored per upload. Per-user unique index on `(file_checksum, user_id)` blocks identical content under different filenames. 409 returns the existing `dataset_id` for client redirect.

**Hand-rolled migration runner**
~20-line runner, `schema_versions` table, numbered SQL files applied in order, each in its own transaction, runs in the FastAPI lifespan hook. No Alembic: the asyncpg-direct stack has no ORM; adding one for migrations alone wasn't justified.

**Async throughout**
asyncpg connection pool + httpx.AsyncClient, both lifespan-managed and injected via FastAPI dependency injection. Event loop never blocked.

**Auth at the database layer**
`get_dataset_owner` checked on every mutating route: 404 first, 403 on mismatch. Metabase treated as a rendering layer only; all access control lives in Dasher's JWT stack.

---

## What shipped

- JWT auth, per-user ownership, 403 on mismatch across all routes
- CSV upload: SHA-256 dedup, filename conflict resolution, original filename persisted
- Statistical profiling cached to Postgres. Downstream reads never touch the CSV again
- LLM semantic inference with confidence scores, force flag, staleness cascade
- Two-pass dashboard planning with post-planning validation and deduplication
- Agentic mode: native function-calling, goal pre-populated from business context
- Two-stage self-healing with LLM diagnosis, healed/failed diff surfaced in UI
- Natural language chart authoring (add, edit, delete) post-build
- Two-turn NL insight engine: stats-mode (no row-level data) or live SQL execution
- Public sharing: owner-toggled, open endpoint, Metabase dashboard ID never exposed
- Hand-rolled migration runner, auto-applied on startup
- Full session rehydration from prior pipeline state
- LLM-agnostic via LiteLLM. Provider swap is a one-line config change
- Validated across 5 structurally distinct datasets including 260K and 220K row CSVs

---

## API reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | Open | Register, returns user_id and role |
| POST | `/auth/login` | Open | Returns JWT access_token |
| POST | `/upload-csv` | Required | Upload CSV, load to Postgres, sync Metabase |
| GET | `/datasets` | Required | List datasets for authenticated user |
| DELETE | `/datasets/{id}` | Required | Delete dataset, dashboard, and all records |
| GET | `/datasets/{id}/state` | Required | Full pipeline state for rehydration |
| GET | `/datasets/{id}/public` | Open | Public embed URL if published, 404 otherwise |
| POST | `/datasets/{id}/publish` | Required | Toggle published state |
| POST | `/infer-dataset-semantics/{id}` | Required | LLM semantic inference, cached |
| POST | `/generate-dashboard-plan/{id}` | Required | Two-pass LLM dashboard plan |
| POST | `/create-metabase-dashboard/{id}` | Required | Idempotent dashboard build with self-healing |
| POST | `/datasets/{id}/dashboard/charts` | Required | Add chart via natural language |
| PUT | `/datasets/{id}/dashboard/charts/{card_id}` | Required | Edit chart via natural language |
| DELETE | `/datasets/{id}/dashboard/charts/{card_id}` | Required | Delete chart |
| POST | `/datasets/{id}/insights` | Required | Two-turn NL insight generation |
| GET | `/datasets/{id}/insights` | Required | Insight history |
| DELETE | `/datasets/{id}/insights/{insight_id}` | Required | Delete insight |

---

## Local setup

**Prerequisites:** Python 3.11+, Node.js, Docker Desktop, PostgreSQL on 5432, LLM provider API key

```bash
git clone <repo>
cd dasher
python -m venv env && env\Scripts\activate        # Windows
pip install -r backend/requirements.txt
# fill in backend/.env (see table below)
docker compose up                                  # starts FastAPI + Metabase
# migrations run automatically on startup
npm run dev --prefix frontend
```

### Environment variables

| Variable | Description |
|----------|-------------|
| `UPLOAD_DIR` | Path to CSV upload directory |
| `LLM_API_KEY` | LLM provider API key |
| `LLM_MODEL` | LiteLLM model string, e.g. `gemini/gemini-3.1-flash-lite` |
| `DATABASE_URL` | Postgres connection string |
| `METABASE_URL` | Internal Metabase URL for FastAPI API calls (e.g. `http://host.docker.internal:3000`) |
| `METABASE_PUBLIC_URL` | Browser-facing Metabase URL for iframe embeds (e.g. `http://localhost:3000`) |
| `METABASE_USERNAME` | Metabase admin username |
| `METABASE_PASSWORD` | Metabase admin password |
| `METABASE_DB_NAME` | Database name as it appears in Metabase |
| `JWT_SECRET` | JWT signing secret |
| `JWT_ALGORITHM` | JWT algorithm (default: HS256) |
| `JWT_EXPIRY_HOURS` | Token expiry in hours (default: 24) |
| `DB_POOL_MIN` | asyncpg pool min connections (default: 2) |
| `DB_POOL_MAX` | asyncpg pool max connections (default: 10) |

---

## Roadmap

- [ ] SSE streaming: real-time agent progress, DB-backed disconnect resumption
- [ ] UI overhaul: one-shot launch card, sidebar dataset picker, per-card iframe grid
- [ ] OpenTelemetry: per-call latency and cost attribution across pipeline stages
- [ ] LLM evals harness: classification confidence, chart build success rate, plan relevance
- [ ] Cloud deployment: Railway, S3/R2 for CSV storage
- [ ] Security hardening: server-side Metabase iframe proxy, permissions lockdown
- [ ] MCP server: Dasher pipeline exposed as MCP tools for Claude Desktop and other agents