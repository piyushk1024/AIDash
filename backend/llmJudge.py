"""
judgeCharts.py — LLM-as-judge quality scoring for Dasher-built charts.

Standalone evaluation script, separate from (and run sooner than) the
Step 10 regression eval harness. Scores every chart in a dataset's most
recent dashboard build — pipeline or agent, whichever ran last — against
that dataset's own profile and (for agent runs) its stated goal.

Nothing here is specific to any one dataset: profile, semantics, and chart
specs are all pulled dynamically for whatever --dataset-id is passed, and
the judge prompt carries no domain assumptions of its own — it only ever
reasons over what this run's profile/semantics/chart actually contain.

Usage:
    python judgeCharts.py --dataset-id <uuid>
    python judgeCharts.py --dataset-id <uuid> --sample-rows

    --sample-rows re-executes each chart's SQL against Metabase and feeds
    the live result rows to the judge too — slower (one extra Metabase
    round-trip per chart) but lets the judge catch cases where the SQL
    runs fine but returns something nonsensical for the chart type.

Requires the same .env as the main app (DATABASE_URL, METABASE_*, LLM_*).
"""

import argparse
import asyncio
import json
import sys
import types
import asyncpg

import httpx

from app.config import settings
from app.services.database import (
    create_pool,
    get_cached_dashboard_plan,
    get_cached_profile,
    get_cached_semantics,
    _init_connection
)
from app.services.metabaseClient import get_session_token, get_database_id, execute_sql_query
from app.services.llm import generate


JUDGE_PROMPT_TEMPLATE = """You are evaluating the quality of a single chart that was auto-generated
for a business dashboard. Judge it strictly on its own merits — do not assume
domain knowledge beyond what's given below.

DATASET PROFILE (column names, types, and summary stats):
{profile_summary}

COLUMN SEMANTIC ROLES (as classified by the system under test):
{semantics_summary}

DASHBOARD GOAL (may be empty if no goal was set):
{goal}

CHART UNDER REVIEW:
  Title: {chart_title}
  Type: {chart_type}
  SQL: {chart_sql}
  X axis: {x_alias}
  Y axis: {y_alias}
{sample_rows_block}

Score this chart on three dimensions, each 1-5 (5 = excellent):

1. RELEVANCE — does this chart serve the stated goal (or, if no goal, does
   it surface a plausible business-relevant question about this data)?
2. CORRECTNESS — does the SQL match the chart's stated intent? Right
   aggregation, right grain, right columns for the chart type? Does the
   chart type suit the shape of the result (e.g. a single row shouldn't be
   a bar chart; a time series should use a date column on x)?
3. CLARITY — is the chart title clear, and would a non-technical viewer
   understand what they're looking at?

Respond with ONLY a JSON object, no markdown fences, no commentary:
{{
  "relevance": <1-5>,
  "correctness": <1-5>,
  "clarity": <1-5>,
  "justification": "<one or two sentences, specific to this chart>"
}}
"""


def summarize_profile(profile: dict, max_cols: int = 30) -> str:
    """Same shape the agent's own _build_profile_summary uses — kept
    generic so this works unchanged for whatever profile_csv() produces."""
    lines = []
    for col in profile.get("columns", [])[:max_cols]:
        name = col.get("column_name", "?")
        stats = col.get("stats", {})
        lines.append(f"  - {name}: {stats}")
    return "\n".join(lines) if lines else "  (no profile columns found)"


def summarize_semantics(semantics: dict) -> str:
    lines = []
    for category in ("date_columns", "dimensions", "measures", "flags", "identifiers"):
        cols = semantics.get(category, [])
        if cols:
            names = ", ".join(c["column"] for c in cols)
            lines.append(f"  - {category}: {names}")
    return "\n".join(lines) if lines else "  (no semantics found)"


def extract_charts(plan: dict) -> tuple[list[dict], str]:
    """
    Works for both pipeline and agent plans without assuming which mode
    produced them — both store a 'charts' list with chart_title/chart_type/
    sql; only agent plans additionally carry a top-level 'goal'.
    """
    mode = plan.get("mode", "pipeline")
    goal = plan.get("goal", "") if mode == "agent" else ""
    charts = plan.get("charts", [])
    return charts, goal


async def fetch_sample_rows(token, http_client, database_id, sql, limit=5) -> str:
    try:
        result = await execute_sql_query(token, http_client, sql, database_id)
        rows = result["rows"][:limit]
        if not rows:
            return "  (query returned no rows)"
        return json.dumps(rows, default=str, indent=2)
    except Exception as e:
        return f"  (query failed at judge time: {e})"


async def judge_chart(profile_summary, semantics_summary, goal, chart, sample_rows_block) -> dict:
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        profile_summary=profile_summary,
        semantics_summary=semantics_summary,
        goal=goal or "(none set)",
        chart_title=chart.get("chart_title", "?"),
        chart_type=chart.get("chart_type", "?"),
        chart_sql=chart.get("sql", "?"),
        x_alias=chart.get("x_alias", "—"),
        y_alias=chart.get("y_alias", "—"),
        sample_rows_block=f"  Sample result rows:\n{sample_rows_block}\n" if sample_rows_block else "",
    )
    raw = (await generate(prompt, stage="judge")).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "relevance": None, "correctness": None, "clarity": None,
            "justification": f"PARSE ERROR — raw response: {raw[:200]}",
        }


def print_report(dataset_id: str, goal: str, scored: list[dict]):
    print(f"\n---\n## Chart Quality Report — dataset {dataset_id}\n")
    if goal:
        print(f"Goal: _{goal}_\n")
    print("| Chart | Relevance | Correctness | Clarity | Justification |")
    print("|---|---|---|---|---|")
    for s in scored:
        print(f"| {s['chart_title']} | {s['relevance']} | {s['correctness']} | {s['clarity']} | {s['justification']} |")

    def avg(key):
        vals = [s[key] for s in scored if isinstance(s[key], (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else "—"

    print(f"\n**Averages** — relevance: {avg('relevance')}, correctness: {avg('correctness')}, clarity: {avg('clarity')}")


async def main_async(dataset_id: str, sample_rows: bool):
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL_LOCAL,
        min_size=settings.DB_POOL_MIN,
        max_size=settings.DB_POOL_MAX,
        init=_init_connection,
    )

    profile = await get_cached_profile(pool, dataset_id)
    semantics_row = await get_cached_semantics(pool, dataset_id)
    plan = await get_cached_dashboard_plan(pool, dataset_id)

    if not plan:
        print(f"ERROR: no dashboard plan found for dataset {dataset_id}. Build a dashboard first.", file=sys.stderr)
        sys.exit(1)
    if not profile:
        print(f"ERROR: no cached profile found for dataset {dataset_id}.", file=sys.stderr)
        sys.exit(1)

    semantics = semantics_row["semantics_json"] if semantics_row else {}
    charts, goal = extract_charts(plan)

    if not charts:
        print(f"No charts found in the most recent plan for dataset {dataset_id}.", file=sys.stderr)
        sys.exit(1)

    profile_summary = summarize_profile(profile)
    semantics_summary = summarize_semantics(semantics)

    token = database_id = http_client = None
    if sample_rows:
        http_client = httpx.AsyncClient(timeout=30.0)
        app_state = types.SimpleNamespace(metabase_token=None, metabase_token_expires=0)
        token = await get_session_token(http_client, app_state)
        database_id = await get_database_id(token, http_client)

    scored = []
    for chart in charts:
        sample_block = ""
        if sample_rows and chart.get("sql"):
            sample_block = await fetch_sample_rows(token, http_client, database_id, chart["sql"])

        result = await judge_chart(profile_summary, semantics_summary, goal, chart, sample_block)
        result["chart_title"] = chart.get("chart_title", "?")
        scored.append(result)
        print(f"  scored: {result['chart_title']}", file=sys.stderr)

    if http_client:
        await http_client.aclose()

    print_report(dataset_id, goal, scored)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", required=True, help="Dataset UUID to evaluate")
    parser.add_argument("--sample-rows", action="store_true",
                         help="Re-execute each chart's SQL against Metabase and include "
                              "live result rows in the judge prompt (slower, more thorough)")
    args = parser.parse_args()
    asyncio.run(main_async(args.dataset_id, args.sample_rows))


if __name__ == "__main__":
    main()