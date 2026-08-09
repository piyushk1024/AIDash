# Dasher

Upload a CSV. Get a fully configured, interactive dashboard in minutes.
No column mapping, no chart config, no BI expertise required, no third-party
BI tool to stand up and maintain.

**Stack:** FastAPI · React/Tailwind · PostgreSQL · react-plotly.js · LiteLLM · Gemini 3.1 Flash-Lite · asyncpg · httpx · PyJWT · OpenTelemetry

> Built with Claude as a development accelerator. Architecture decisions, product tradeoffs, and validation are the author's own.

---

Dasher is an AI-enabled dashboarding tool and portfolio project built to demonstrate
agentic AI patterns, production-grade API design, and end-to-end system thinking.
It runs two build modes: a sequential pipeline (profile → semantics → plan → build)
and an agentic mode where an LLM orchestrates the same pipeline via native
function-calling with no LangChain dependency, streaming its progress to the client
in real time over SSE. Both modes render a fully interactive, shareable dashboard
directly from a raw CSV upload, natively, with no external BI service in the
rendering path. Either mode can be rebuilt independently without destroying the other.

## The problem

Getting from raw data to a useful dashboard requires manually mapping columns,
choosing chart types, writing queries, and configuring a BI tool. It demands
both domain knowledge and BI expertise. Most people skip it.
Dasher automates the full chain: statistical profiling, LLM semantic inference,
dashboard planning, and native chart rendering. The only input required is a
CSV and an optional one-line description of the data.

---

## What it does

1. Upload a CSV, profiled automatically (stats, value counts, correlations)
2. LLM classifies every column: dimensions, measures, dates, flags, identifiers
3. Two-pass dashboard planning: analytical questions first, then charts
4. PostgreSQL-native charts executed and rendered natively via Plotly, no external BI dependency
5. Agentic build mode streams live progress (inspect/build/heal/finish) over SSE, closing with an agent-authored rationale explaining why the dashboard fits the stated goal
6. Natural language authoring: add, edit, or delete charts post-build, right on the chart grid
7. Natural language insight engine against live data
8. One-click public sharing, frozen at publish time

---

## Engineering highlights

**Thirteen chart types across two tiers**
Tier A (scalar, bar, row, line, pie, scatter, histogram, box, table) uses structured
`x/y/series` aliases; Dasher builds the Plotly spec itself. Tier B (gauge, funnel,
waterfall, map) is fully LLM-driven: the model computes its own thresholds, bands,
or stage breakdowns via SQL and supplies the visualization config directly, with
self-healing as the correctness net rather than a hardcoded template per type.
Pivot is excluded by design: it doesn't map cleanly onto Dasher's native-SQL,
single-query-per-chart architecture.

**Native rendering, zero BI-tool dependency**
Charts render directly from query results via Plotly, no embedded third-party BI
service, no iframe, no separate rendering process to provision, secure, or keep in
sync. A dashboard is just SQL results and a JSON spec, all the way down.

**Non-destructive rebuild**
Dashboard rebuilds diff against the previous build rather than tearing down and
recreating every chart. Unchanged charts are skipped entirely, changed charts are
updated in place, only removed charts are dropped.

**Mode-aware dashboard state**
Pipeline and agent builds are tracked independently. Rebuilding one mode never
silently corrupts or orphans the other's live dashboard. Switching modes is an
explicit, confirmed action, not a race condition.

**Agent-exclusive dashboard rationale**
After an agentic build finishes, a dedicated synthesis step generates a short,
plain-language explanation of why the resulting dashboard fits the stated goal,
narration-free and specific to what was actually built. A visible, no-extra-clicks
differentiator between Standard and Agentic mode.

**O(columns) not O(rows) LLM cost**
The LLM receives a statistical profile, not raw rows. Token usage scales with
schema width, not dataset size. 

**AST-based SQL validation**
Every LLM-generated query is parsed to an AST via sqlglot before execution, not
pattern-matched against a keyword blocklist. The parser enforces a single
statement, requires the root node to be a `Select` (CTEs included), and walks the
full tree rejecting any disallowed node type: `Insert`, `Update`, `Delete`, `Drop`,
`Alter`, `Create`, `TruncateTable`, `Grant`, `Command`. Structural validation, not
string matching.

**Native SQL generation**
Raw PostgreSQL generated directly: window functions, CTEs, percentiles, HAVING,
derived metrics, top-N. No query abstraction layer constraining expressiveness.

**Agentic mode with native function-calling**
An LLM agent orchestrates the full pipeline via native Gemini function-calling,
no LangChain or LangGraph. Tools: `inspect_data`, `build_and_add_chart`,
`edit_existing_chart`, `delete_existing_chart`, `finish`. Agent goal is
pre-populated from the business context set at upload time, editable before launch.

**Real-time agent streaming**
The agent loop is an async generator (`stream_agent`) yielding typed events
(`step_started`, `inspect_result`, `chart_built`, `healing`, `rationale`, `finish`)
over Server-Sent Events. Each trace-worthy event is persisted before the next step
runs, so a client disconnect mid-run is recoverable: `GET /datasets/{id}/state`
returns the partial trace and whatever charts had already landed. The existing
synchronous endpoint is preserved as a thin wrapper over the same generator.

**Two-stage self-healing**
Chart failures caught at two levels: build failures and rendering failures. Both
trigger an automated LLM-powered heal cycle, covering SQL errors and Tier B
visualization config errors alike. Healed charts flagged in UI with a before/after
comparison.

**Static, frozen public sharing**
Publishing snapshots the query results and Plotly spec at that moment, no live
re-query on the public route. Underlying data exposure is eliminated by
construction, not by an access-control check someone could get wrong.

**Semantics staleness cascade**
Re-running semantic inference with a changed hint marks the downstream plan stale
via `stale` + `generation_counter`. The `force` flag bypasses the LLM cache without
triggering staleness. Hint change and forced refresh are handled as distinct cases.

**Zero CSV footprint**
The uploaded file is read once, loaded straight into Postgres, and discarded, no
disk write, no database blob. Every downstream stage, both build modes, reads from
the statistical profile cached in Postgres. Storage cost stays flat regardless of
upload volume.

**Hand-rolled migration runner**
~20-line runner, `schema_versions` table, numbered SQL files applied in order,
each in its own transaction, runs in the FastAPI lifespan hook. No Alembic: the
asyncpg-direct stack has no ORM, adding one for migrations alone wasn't justified.

**OpenTelemetry instrumentation**
Spans on every LLM call (`generate()` / `generate_with_tools()`) carrying `stage`,
`model`, `input_tokens`, `output_tokens`, and `latency_ms`. Per-stage cost and
latency attribution across the full pipeline without touching business logic.

**Async throughout**
asyncpg connection pool + httpx.AsyncClient, both lifespan-managed and injected via
FastAPI dependency injection. Event loop never blocked on the request path.

**Auth at the database layer**
`get_dataset_owner` checked on every mutating route: 404 first, 403 on mismatch.
All access control lives in Dasher's own JWT stack, nothing delegated to a
rendering layer. Verified with a dedicated cross-user access test suite covering
every dataset-scoped route.

---

## What shipped

- JWT auth, per-user ownership, 403 on mismatch across all routes
- CSV upload: original filename persisted, file discarded after load, zero storage footprint
- Statistical profiling cached to Postgres for both build modes
- LLM semantic inference with confidence scores, force flag, staleness cascade
- Two-pass dashboard planning with post-planning validation and deduplication
- Thirteen-type, two-tier chart system, natively rendered via Plotly with zero third-party BI dependency
- Non-destructive, diff-based dashboard rebuilds
- Agentic mode: native function-calling, goal pre-populated from business context, closing rationale synthesis
- Real-time SSE streaming for agent builds, with disconnect resumption
- Two-stage self-healing with LLM diagnosis, covering both SQL and viz config errors
- Natural language chart authoring (add, edit, delete) directly on the chart grid
- Two-turn NL insight engine: stats-mode (no row-level data) or live SQL execution
- Static, frozen public sharing: owner-toggled, no live re-query on the public route
- Hand-rolled migration runner, auto-applied on startup
- Full session rehydration from prior pipeline state, mode-aware (pipeline vs agent)
- OpenTelemetry spans across the LLM pipeline: per-stage cost and latency attribution
- LLM-agnostic via LiteLLM, provider swap is a one-line config change
- AST-based SQL validation via sqlglot, structural not pattern-based
- Downloadable PDF export of agent-built dashboards
- One-shot launch UI: sidebar dataset picker, per-card workspace grid
- Validated across 5 structurally distinct datasets including 260K and 220K row CSVs

---

## API reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | Open | Register, returns user_id and role |
| POST | `/auth/login` | Open | Returns JWT access_token |
| POST | `/upload-csv` | Required | Upload CSV, load to Postgres, profile |
| GET | `/datasets` | Required | List datasets for authenticated user |
| DELETE | `/datasets/{id}` | Required | Delete dataset, dashboard, and all records |
| GET | `/datasets/{id}/state` | Required | Full pipeline state for rehydration |
| GET | `/datasets/{id}/public` | Open | Public snapshot if published, 404 otherwise |
| POST | `/datasets/{id}/publish` | Required | Toggle published state, mode-aware |
| POST | `/infer-dataset-semantics/{id}` | Required | LLM semantic inference, cached |
| POST | `/generate-dashboard-plan/{id}` | Required | Two-pass LLM dashboard plan |
| POST | `/datasets/{id}/dashboard/build` | Required | Diff-based, self-healing dashboard build |
| POST | `/datasets/{id}/dashboard/agent` | Required | Agentic build, synchronous |
| POST | `/datasets/{id}/dashboard/agent/stream` | Required | Agentic build, SSE streaming with disconnect resumption |
| POST | `/datasets/{id}/dashboard/charts` | Required | Add chart via natural language |
| PUT | `/datasets/{id}/dashboard/charts/{card_id}` | Required | Edit chart via natural language |
| DELETE | `/datasets/{id}/dashboard/charts/{card_id}` | Required | Delete chart |
| POST | `/datasets/{id}/insights` | Required | Two-turn NL insight generation |
| GET | `/datasets/{id}/insights` | Required | Insight history |
| DELETE | `/datasets/{id}/insights/{insight_id}` | Required | Delete insight |

---

## Local setup

**Prerequisites:** Python 3.11+, Node.js, Docker Engine, PostgreSQL on 5432, LLM provider API key

```bash
git clone <repo>
cd dasher
python -m venv env && source env/bin/activate
pip install -r backend/requirements.txt
# fill in backend/.env (see table below)
docker compose up                                  # starts Postgres + FastAPI
# migrations run automatically on startup
npm run dev --prefix frontend
```

### Environment variables

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | LLM provider API key |
| `LLM_MODEL` | LiteLLM model string, e.g. `gemini/gemini-3.1-flash-lite` |
| `DATABASE_URL` | Postgres connection string |
| `JWT_SECRET` | JWT signing secret |
| `JWT_ALGORITHM` | JWT algorithm (default: HS256) |
| `JWT_EXPIRY_HOURS` | Token expiry in hours (default: 24) |
| `DB_POOL_MIN` | asyncpg pool min connections (default: 2) |
| `DB_POOL_MAX` | asyncpg pool max connections (default: 10) |

---

## Roadmap

- [x] SSE streaming: real-time agent progress, disconnect resumption
- [x] OpenTelemetry: per-call latency and cost attribution across pipeline stages
- [x] Two-tier chart type system with LLM-driven Tier B visualization config
- [x] Non-destructive, diff-based dashboard rebuilds
- [x] Native Plotly rendering, removing the Metabase dependency entirely
- [x] Agent-exclusive dashboard rationale synthesis
- [x] Scatter, histogram, and box plot chart types
- [x] Postman collection: full pipeline chain (upload → semantics → build) with environment-based dataset_id threading
- [x] CI: ruff, eslint, pytest gating on push
- [x] AST-based SQL validation via sqlglot
- [x] Provider-unavailability (503) surfacing across both build paths
- [x] Downloadable PDF export of agent-built dashboards
- [x] One-shot launch UI: sidebar dataset picker, per-card workspace grid
- [ ] LLM-as-judge chart quality evaluation
- [ ] LLM evals harness: classification confidence, chart build success rate, plan relevance
- [ ] Cloud deployment
- [ ] MCP server: Dasher pipeline exposed as MCP tools for Claude Desktop and other agents