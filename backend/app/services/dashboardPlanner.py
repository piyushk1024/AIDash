import json
from google import genai
from app.config import settings
from app.services.sqlGuard import validate_sql

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _build_chartable_context(semantics: dict, profile: dict, field_map: dict) -> tuple[set, dict, list]:
    """
    Returns (chartable_cols, filtered_field_map, filtered_profile_columns).
    Filters all three to chartable columns only before passing to the LLM.
    """
    chartable_cols = {
        col["column"]
        for category in ("date_columns", "dimensions", "measures", "flags")
        for col in semantics.get(category, [])
        if col.get("chartable")
    }

    filtered_field_map = {
        col: meta for col, meta in field_map.items()
        if col in chartable_cols
    }

    filtered_profile_cols = [
        col for col in profile.get("columns", [])
        if col["column_name"] in chartable_cols
    ]

    return chartable_cols, filtered_field_map, filtered_profile_cols


def _build_field_reference(filtered_field_map: dict, semantics: dict) -> str:
    role_map = {}
    for category in ("date_columns", "dimensions", "measures", "flags", "identifiers", "unknown"):
        for col in semantics.get(category, []):
            role_map[col["column"]] = col["semantic_role"]

    return "\n".join(
        f'  - "{col}" | {meta["base_type"]} | {role_map.get(col, "unknown")}'
        for col, meta in filtered_field_map.items()
    )


PLANNER_PROMPT = """
You are a BI analyst planning a Metabase dashboard using PostgreSQL native SQL queries.

Table: "{table_name}"

Available columns (name | base_type | semantic_role):
{field_reference}

Dataset profile (stats, value_counts, correlations, grouped_stats):
{profile_summary}

---

Reasoning pass:
Before planning charts, identify the 5 to 7 most analytically interesting questions 
this dataset can answer. Consider:
- Rankings and extremes (top/bottom performers)
- Distributions across categorical dimensions
- Trends over time where date columns exist
- Correlations between measures
- Derived metrics: ratios, rates, percentages computed in SQL
- Statistical spread: percentiles, variance
- Comparative analysis: how does one segment differ from another

Chart planning pass:
For each question, plan one chart. Write PostgreSQL SQL that answers it directly.
Alias all output columns clearly — Metabase uses aliases as axis labels.

HARD CONSTRAINTS — non-negotiable:
- Only use columns from the available columns list above
- Double-quote all column and table names
- PostgreSQL syntax only
- SELECT only — never emit DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- No semicolons
- chart_type must match the SQL output shape:
    - scalar: query returns exactly one row, one column
    - bar, line, pie: first column is dimension, second column is measure
- No two charts may have the same chart_title

POSTGRESQL CAPABILITIES — use these where analytically justified:
- Window functions: RANK() OVER, SUM() OVER, AVG() OVER (PARTITION BY / ORDER BY)
- Date truncation: DATE_TRUNC('month', "date_col") for time series
- Percentiles: PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "col")
- Post-aggregation filtering: HAVING
- Staged queries: CTEs (WITH ... AS (...) SELECT ...)
- Conditional bucketing: CASE WHEN ... THEN ... END
- Top-N: ORDER BY ... LIMIT N
- ROUND("col"::numeric, 2) for decimal formatting

Return ONLY a JSON object with exactly these fields:
{{
  "dataset_id": "{dataset_id}",
  "dashboard_title": "string",
  "charts": [
    {{
      "chart_title": "string",
      "chart_type": "bar" | "line" | "scalar" | "pie",
      "sql": "SELECT ...",
      "x_alias": "exact column alias used for the dimension in the SQL, null for scalar",
      "y_alias": "exact column alias used for the measure in the SQL, null for scalar",
      "reasoning": "one sentence tying this chart to a specific analytical question"
    }}
  ]
}}

Aim for 5 to 7 charts. Raw JSON only, no markdown.
"""


def generate_dashboard_plan(
    dataset_id: str,
    semantics: dict,
    profile: dict,
    table_name: str,
    field_map: dict,
) -> dict:

    chartable_cols, filtered_field_map, filtered_profile_cols = _build_chartable_context(
        semantics, profile, field_map
    )

    field_reference = _build_field_reference(filtered_field_map, semantics)

    profile_summary = {
        "columns": filtered_profile_cols,
        "grouped_stats": profile.get("grouped_stats", {}),
    }

    prompt = PLANNER_PROMPT.format(
        table_name=table_name,
        dataset_id=dataset_id,
        field_reference=field_reference,
        profile_summary=json.dumps(profile_summary, indent=2),
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
    )

    raw = response.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    parsed = json.loads(raw)
    parsed["dataset_id"] = dataset_id

    # Validate SQL for each chart — drop charts that fail the guard
    safe_charts = []
    for chart in parsed.get("charts", []):
        try:
            validate_sql(chart["sql"], context=chart.get("chart_title", ""))
            safe_charts.append(chart)
        except ValueError:
            pass

    parsed["charts"] = safe_charts
    return parsed