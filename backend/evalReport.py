"""
evalReport.py — combined eval report for Dasher: cost faceoff + chart quality judge.

Replaces llmJudge.py and costValidation.py, both broken post-Metabase-removal
(llmJudge imported dead metabaseClient functions; costValidation called
profile_csv() with the old file-path signature instead of the current
Postgres-backed one).

For each fixture CSV, this script:
  1. Loads it into Postgres through the real upload path (load_csv_to_postgres),
     same as a live upload.
  2. Cost faceoff — profiles it via profile_csv() (Dasher's O(columns) approach)
     vs a naive full-row CSV dump, same prompt, compares token/cost usage.
  3. Runs the actual production pipeline (stream_pipeline: semantics -> plan ->
     build with self-healing) to get real built charts with real query rows.
  4. LLM-judges each built chart on relevance/correctness/clarity.
  5. Drops the temp table and dataset row (unless --keep-data).

The app's daily quota gate (app.services.llm.check_quota/increment_usage) is
FK-tied to a real authenticated user, which a standalone script doesn't have.
This script patches those two functions to no-ops before importing anything
that calls generate() — every other line of semantics/plan/build/heal logic
is the real, unmodified app code path.

Usage:
    python evalReport.py --csv eval_fixtures/sales.csv --csv eval_fixtures/survey.csv
    python evalReport.py --csv eval_fixtures/sales.csv --keep-data

Requires the same .env as the main app (DATABASE_URL or DATABASE_URL_LOCAL, LLM_*).
"""
from app.services.database import _init_connection, delete_dataset
from app.services.csvLoader import load_csv_to_postgres, sanitise_table_name
from app.services.profiler import profile_csv
from app.services.llmClient import build_semantics_prompt
import app.services.pipelineOrchestrator as pipeline_module
from app.services.pipelineOrchestrator import stream_pipeline

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import litellm
import pandas as pd

from app.config import settings

# ── Patch the quota gate before importing anything that calls generate() ──
import app.services.llm as llm_module


async def _noop_quota(*args, **kwargs):
    return None


llm_module.reserve_quota_slot = _noop_quota
llm_module.refund_quota_slot = _noop_quota



pipeline_module.get_current_user_quota = _noop_quota

PRICE_PER_1M_INPUT = 0.10   # USD — verify against provider pricing before citing
PRICE_PER_1M_OUTPUT = 0.40  # USD

JUDGE_PROMPT_TEMPLATE = """You are evaluating the quality of a single chart that was auto-generated
for a business dashboard. Judge it strictly on its own merits.

DATASET PROFILE (column names, types, and summary stats):
{profile_summary}

CHART UNDER REVIEW:
  Title: {chart_title}
  Type: {chart_type}g
  SQL: {chart_sql}
  X axis: {x_alias}
{y_alias_line}  Sample result rows:

Score this chart on three dimensions, each 1-5 (5 = excellent):
1. RELEVANCE — does it surface a plausible, business-relevant question about this data?
2. CORRECTNESS — does the SQL match the chart's stated intent? Right aggregation,
   right grain, right chart type for the result shape?
3. CLARITY — is the title clear, would a non-technical viewer understand it?

Respond with ONLY a JSON object, no markdown fences, no commentary:
{{
  "relevance": <1-5>,
  "correctness": <1-5>,
  "clarity": <1-5>,
  "justification": "<one or two sentences, specific to this chart>"
}}
"""
_RETRY_DELAY_PATTERN = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')
MAX_RETRIES = 5
DEFAULT_RETRY_SECONDS = 20.0


async def call_llm_direct(prompt: str) -> dict:
    """Bypasses app.services.llm.generate() entirely — no quota, no OTel span.
    Used for the cost faceoff (raw token/cost comparison) and the judge
    (offline scoring), neither of which is part of the app's own
    request-serving path. Free-tier rate limits (15 req/min) are easy to hit
    across a full fixture run, so this does its own retry/backoff — same
    retryDelay-parsing pattern as app.services.llm._start_cooldown, just
    local to this call instead of a process-wide cooldown."""
    for attempt in range(MAX_RETRIES):
        try:
            response = await litellm.acompletion(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                api_key=settings.LLM_API_KEY,
            )
            break
        except litellm.RateLimitError as e:
            if attempt == MAX_RETRIES - 1:
                raise
            match = _RETRY_DELAY_PATTERN.search(str(e))
            delay = float(match.group(1)) if match else DEFAULT_RETRY_SECONDS
            print(f"    rate limited, retrying in {delay:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})...", file=sys.stderr)
            await asyncio.sleep(delay)

    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    cost = (
        (input_tokens / 1_000_000) * PRICE_PER_1M_INPUT
        + (output_tokens / 1_000_000) * PRICE_PER_1M_OUTPUT
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "response": response.choices[0].message.content.strip(),
    }

def summarize_profile(profile: dict, max_cols: int = 30) -> str:
    lines = []
    for col in profile.get("columns", [])[:max_cols]:
        name = col.get("column_name", "?")
        stats = col.get("stats", {})
        lines.append(f"  - {name}: {stats}")
    return "\n".join(lines) if lines else "  (no profile columns found)"


_Y_ALIAS_CHART_TYPES = {"bar", "row", "line", "scatter", "box"}


def _json_safe(value):
    # asyncpg returns Postgres NUMERIC as Decimal, which json.dumps can't
    # serialize natively. A bare default=str stringifies it, which json
    # then re-quotes — so "1200.50" shows up as a JSON *string* to the
    # judge, making a genuinely numeric column look like text. Convert
    # Decimal to float explicitly instead, so the judge sees real numbers.
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


async def judge_chart(profile_summary: str, chart: dict) -> dict:
    rows = chart.get("rows") or []
    sample_block = json.dumps(rows[:5], default=_json_safe, indent=2) if rows else "  (no rows)"

    chart_type = chart.get("chart_type", "?")
    # y_alias only means something for chart types that actually plot it —
    # histogram/scalar/table/sankey/gauge/funnel ignore it entirely in
    # queryExecutor.py, so showing it there just gives the judge a stray
    # field to (incorrectly) flag as a rendering bug.
    y_alias_line = f"  Y axis: {chart.get('y_alias', '—')}\n" if chart_type in _Y_ALIAS_CHART_TYPES else ""

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        profile_summary=profile_summary,
        chart_title=chart.get("chart_title", "?"),
        chart_type=chart_type,
        chart_sql=chart.get("sql", "?"),
        x_alias=chart.get("x_alias", "—"),
        y_alias_line=y_alias_line,
        sample_rows_block=sample_block,
    )

    result = await call_llm_direct(prompt)
    raw = result["response"]
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        scored = json.loads(raw)
    except json.JSONDecodeError:
        scored = {"relevance": None, "correctness": None, "clarity": None,
                  "justification": f"PARSE ERROR — raw response: {raw[:200]}"}
    scored["chart_title"] = chart.get("chart_title", "?")
    return scored


async def run_cost_faceoff(pool, csv_path: Path, table_name: str, dataset_id: str, naive_rows: int) -> dict:
    print("  [cost] profiling via Dasher pipeline...")
    profile = await profile_csv(pool, table_name, dataset_id)
    context = f"Dataset profile (statistical summary):\n{json.dumps(profile, indent=2, default=str)}"
    dasher_prompt = build_semantics_prompt(context)
    dasher = await call_llm_direct(dasher_prompt)
    dasher["context_chars"] = len(context)

    print(f"  [cost] naive: reading {naive_rows} raw rows...")
    df = pd.read_csv(csv_path, encoding="utf-8-sig").head(naive_rows)
    naive_context = f"Raw dataset ({naive_rows} rows):\n{df.to_csv(index=False)}"
    naive_prompt = build_semantics_prompt(naive_context)
    naive = await call_llm_direct(naive_prompt)
    naive["context_chars"] = len(naive_context)

    return {"profile": profile, "dasher": dasher, "naive": naive}


async def run_pipeline_and_judge(pool, dataset_id: str, table_name: str, field_map: dict, profile: dict) -> list[dict]:
    print("  [pipeline] running semantics -> plan -> build (with self-healing)...")
    built_charts = []
    async for event in stream_pipeline(
        dataset_id=dataset_id, table_name=table_name, field_map=field_map,
        business_hint=None, pool=pool,
    ):
        if event["type"] == "phase_error":
            print(f"  [pipeline] FAILED at {event['phase']}: {event['error']}", file=sys.stderr)
            return []
        if event["type"] == "finish":
            built_charts = event["plan"]["charts"]

    if not built_charts:
        print("  [pipeline] no charts built.", file=sys.stderr)
        return []

    print(f"  [judge] scoring {len(built_charts)} built charts...")
    profile_summary = summarize_profile(profile)
    scored = []
    for chart in built_charts:
        result = await judge_chart(profile_summary, chart)
        scored.append(result)
        print(f"    scored: {result['chart_title']}", file=sys.stderr)
    return scored


def print_report(csv_path: Path, cost: dict, judged: list[dict], naive_rows: int):
    dasher, naive = cost["dasher"], cost["naive"]
    total_rows = len(pd.read_csv(csv_path, encoding="utf-8-sig"))
    ratio = round(naive["input_tokens"] / dasher["input_tokens"], 1) if dasher["input_tokens"] else "—"

    print(f"\n---\n## Eval Report — `{csv_path.name}`\n")
    print(f"Rows: {total_rows:,} | Naive row limit: {naive_rows} | Model: `{settings.LLM_MODEL}`\n")

    print("### Cost faceoff: Dasher profile vs naive row-dump\n")
    print("| | Dasher (profile) | Naive ({} rows) |".format(naive_rows))
    print("|---|---|---|")
    print(f"| Input tokens  | {dasher['input_tokens']:,} | {naive['input_tokens']:,} |")
    print(f"| Output tokens | {dasher['output_tokens']:,} | {naive['output_tokens']:,} |")
    print(f"| Cost (USD)    | ${dasher['cost_usd']:.6f} | ${naive['cost_usd']:.6f} |")
    print(f"| Context chars | {dasher['context_chars']:,} | {naive['context_chars']:,} |")
    print(f"\n**Naive used {ratio}x more input tokens.** Dasher is O(columns); naive is O(rows x columns).\n")

    print("### Chart quality (LLM judge)\n")
    if not judged:
        print("No charts were built for this dataset.\n")
        return
    print("| Chart | Relevance | Correctness | Clarity | Justification |")
    print("|---|---|---|---|---|")
    for s in judged:
        print(f"| {s.get('chart_title', '?')} | {s.get('relevance', '—')} | {s.get('correctness', '—')} | {s.get('clarity', '—')} | {s.get('justification', '—')} |")

    def avg(key):
        vals = [s[key] for s in judged if isinstance(s.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else "—"

    print(f"\n**Averages** — relevance: {avg('relevance')}, correctness: {avg('correctness')}, clarity: {avg('clarity')}")


async def run_one(pool, csv_path: Path, naive_rows: int, keep_data: bool):
    dataset_id = str(uuid4())
    table_name = sanitise_table_name(csv_path.name)
    content = csv_path.read_bytes()

    print(f"[{csv_path.name}] loading into Postgres as \"{table_name}\"...")
    load_result = await load_csv_to_postgres(pool, content, table_name, is_privileged=True)
    field_map = {col: {"base_type": base_type} for col, base_type in load_result["columns"].items()}

    try:
        cost = await run_cost_faceoff(pool, csv_path, table_name, dataset_id, naive_rows)
        judged = await run_pipeline_and_judge(pool, dataset_id, table_name, field_map, cost["profile"])
        print_report(csv_path, cost, judged, naive_rows)
    finally:
        if keep_data:
            print(f"[{csv_path.name}] --keep-data set, leaving dataset_id={dataset_id} in place.", file=sys.stderr)
        else:
            await delete_dataset(pool, dataset_id, table_name)


async def main_async(csv_paths: list[Path], naive_rows: int, keep_data: bool):
    db_url = settings.DATABASE_URL_LOCAL or settings.DATABASE_URL
    pool = await asyncpg.create_pool(
        db_url,
        min_size=settings.DB_POOL_MIN,
        max_size=settings.DB_POOL_MAX,
        init=_init_connection,
    )
    try:
        for csv_path in csv_paths:
            if not csv_path.exists():
                print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
                continue
            await run_one(pool, csv_path, naive_rows, keep_data)
    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", action="append", required=True,
                         help="Path to a fixture CSV. Repeatable.")
    parser.add_argument("--rows", type=int, default=1000,
                         help="Max rows sent in the naive cost comparison (default 1000)")
    parser.add_argument("--keep-data", action="store_true",
                         help="Skip dropping the temp table/dataset row after running")
    args = parser.parse_args()
    csv_paths = [Path(p) for p in args.csv]
    asyncio.run(main_async(csv_paths, args.rows, args.keep_data))


if __name__ == "__main__":
    main()