import json
from app.services.llm import generate
from app.services.sqlGuard import validate_sql
from app.schemas.chartTypes import (
    CHART_TYPE_GUIDANCE,
    CHART_TYPE_VALUES,
    ChartType,
    DIMENSION_MEASURE_TYPES,
    MEASURE_PAIR_TYPES,
    HISTOGRAM_TYPES,
    DISTRIBUTION_TYPES,
)


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

Note on grouped_stats: each categorical grouping includes a "_spread_cv" entry
per numeric column — the coefficient of variation (std / mean) across that
column's group means. A low _spread_cv (below ~0.10) means the groups barely
differ on that measure; a chart built on that pairing will look visually flat
regardless of chart type. Use this to judge which (dimension, measure) pairs
are actually worth charting.

---

Reasoning pass:
Before planning charts, identify the most analytically interesting questions
this dataset can answer — typically 5 to 7, but fewer if the data genuinely
doesn't support that many, more if it's unusually rich. Consider:
- Rankings and extremes (top/bottom performers)
- Distributions across categorical dimensions
- Trends over time where date columns exist
- Correlations between measures
- Derived metrics: ratios, rates, percentages computed in SQL
- Statistical spread: percentiles, variance
- Comparative analysis: how does one segment differ from another
- Multi-factor questions (e.g. "does X vary by Y after accounting for Z") —
  these are usually best answered by one chart combining the relevant
  dimensions (see series_alias below), not several charts that each
  address only one factor

Chart planning pass:
For each question, plan one chart. Write PostgreSQL SQL that answers it directly.
Alias all output columns clearly — Metabase uses aliases as axis labels.

Before finalizing each chart, check _spread_cv for that chart's grouping
column and measure. If it's low (below ~0.10), the comparison is essentially
flat and not worth a chart in that form. Instead:
- pick a different angle on the same columns (a different breakdown, a
  highlight of actual outliers within the group, a ratio/derived metric), or
- reframe it if the flatness itself is the finding (e.g. "failure rate is
  uniform across all services" as a scalar/comparison stat), or
- drop the question and use a different one from the reasoning pass

HARD CONSTRAINTS — non-negotiable:
- Only use columns from the available columns list above
- Double-quote all column and table names
- PostgreSQL syntax only
- SELECT only — never emit DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- No semicolons
- No two charts may have the same chart_title
- chart_type must match the SQL output shape and analytical intent:
{chart_type_guidance}

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
      "chart_type": "one of the valid chart types listed above",
      "sql": "SELECT ...",
      "x_alias": "exact column alias for the dimension, null for scalar/table/passthrough types",
      "y_alias": "exact column alias for the measure, null for scalar/table/passthrough types",
      "series_alias": "optional — second dimension to group/stack by, only for bar/row",
      "viz_params": "optional dict — required for gauge/funnel/waterfall/pivot/map, omit otherwise",
      "reasoning": "one sentence tying this chart to a specific analytical question"
    }}
  ]
}}

Raw JSON only, no markdown.
"""
async def generate_dashboard_plan(
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
        chart_type_guidance=CHART_TYPE_GUIDANCE,
    )

    raw = await generate(prompt, stage="planner")
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    parsed = json.loads(raw)
    parsed["dataset_id"] = dataset_id

    # Validate each chart — drop charts that fail the SQL guard, carry an
    # unrecognised chart_type, or are missing an alias the executor will
    # require anyway. This last check catches at plan time what would
    # otherwise silently force every such chart through a guaranteed
    # healer pass on first build.
    safe_charts = []
    for chart in parsed.get("charts", []):
        chart_type_str = chart.get("chart_type")
        if chart_type_str not in CHART_TYPE_VALUES:
            continue

        chart_type = ChartType(chart_type_str)

        if chart_type in DIMENSION_MEASURE_TYPES or chart_type in MEASURE_PAIR_TYPES:
            if not chart.get("x_alias") or not chart.get("y_alias"):
                continue
        if chart_type in HISTOGRAM_TYPES and not chart.get("x_alias"):
            continue
        if chart_type in DISTRIBUTION_TYPES and not chart.get("y_alias"):
            continue

        try:
            validate_sql(chart["sql"], context=chart.get("chart_title", ""))
            safe_charts.append(chart)
        except ValueError:
            pass

    parsed["charts"] = safe_charts
    return parsed

