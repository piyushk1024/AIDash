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

PIE_MAX_DISTINCT = 10
HISTOGRAM_MIN_DISTINCT = 15
CATEGORY_MAX_DISTINCT = 30
SERIES_MAX_DISTINCT = 10
SANKEY_NODE_MAX_DISTINCT = 15


def _distinct_count_for_alias(profile: dict, alias: str | None) -> int | None:
    # Cardinality/legibility guardrail lookup. Guidance instructs histogram/
    # box/pie/sankey source columns to use a SQL alias matching the source
    # column name, so a direct name match covers the normal case. Fails
    # open (returns None) on any mismatch rather than blocking a chart over
    # an alias the guardrail can't confidently resolve.
    if not alias:
        return None
    for col in profile.get("columns", []):
        if col.get("column_name") == alias:
            return col.get("distinct_count")
    return None

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
You are a BI analyst planning a dashboard using PostgreSQL native SQL queries.

Table: "{table_name}"

Available columns (name | base_type | semantic_role):
{field_reference}

Dataset profile (stats, value_counts, correlations, grouped_stats):
{profile_summary}

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
- Multi-factor comparisons (e.g. how one segment differs from another, or
  "does X vary by Y after accounting for Z") — usually best answered by one
  chart combining the relevant dimensions (see series_alias below), not
  several single-factor charts

Chart planning pass:
For each question, plan one chart. Write PostgreSQL SQL that answers it
directly. Before finalizing, check grouped_stats' "_spread_cv" entry (std /
mean across group means) for that chart's grouping column and measure. Below
~0.10 means the groups barely differ — the comparison will look flat
regardless of chart type. Instead:
- pick a different angle on the same columns (a different breakdown, a
  highlight of actual outliers within the group, a ratio/derived metric), or
- reframe it if the flatness itself is the finding (e.g. "failure rate is
  uniform across all services" as a scalar/comparison stat), or
- drop the question and use a different one from the reasoning pass

HARD CONSTRAINTS — non-negotiable:
- Only use columns from the available columns list above
- Double-quote all column and table names; alias all output columns clearly
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
      "x_label": "optional — display axis title for x_alias, only if the alias itself is a poor label",
      "y_label": "optional — display axis title for y_alias, same rule as x_label",
      "series_alias": "optional — second dimension to group/stack by, only for bar/row/line/scatter/histogram",
      "source_alias": "optional — required for sankey only, exact alias of the source category column",
      "target_alias": "optional — required for sankey only, exact alias of the target category column",
      "value_alias": "optional — required for sankey only, exact alias of the count/weight column",
      "viz_params": "optional dict — required for gauge/funnel only, omit otherwise (including for sankey)",
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

        # Cardinality/legibility guardrail — a chart can pass every alias
        # check above and still be unreadable if the underlying column has
        # too many (pie/bar/row/box/sankey) or too few (histogram) distinct
        # values for that chart type to represent clearly. Runs before the
        # SQL guard below since it's cheap and needs no parsing.
        x_distinct = _distinct_count_for_alias(profile, chart.get("x_alias"))

        if chart_type == ChartType.PIE and x_distinct is not None and x_distinct > PIE_MAX_DISTINCT:
            # Pie and bar share the same SQL shape (one dimension + one
            # measure, already grouped) — downgrade in place instead of
            # dropping, no re-query needed.
            chart["chart_type"] = ChartType.BAR.value
            chart_type = ChartType.BAR

        if chart_type in HISTOGRAM_TYPES and x_distinct is not None and x_distinct < HISTOGRAM_MIN_DISTINCT:
            continue

        if chart_type in (ChartType.BAR, ChartType.ROW, ChartType.BOX) and x_distinct is not None and x_distinct > CATEGORY_MAX_DISTINCT:
            continue

        series_distinct = _distinct_count_for_alias(profile, chart.get("series_alias"))
        if series_distinct is not None and series_distinct > SERIES_MAX_DISTINCT:
            continue

        if chart_type == ChartType.SANKEY:
            source_distinct = _distinct_count_for_alias(profile, chart.get("source_alias"))
            target_distinct = _distinct_count_for_alias(profile, chart.get("target_alias"))
            if (source_distinct is not None and source_distinct > SANKEY_NODE_MAX_DISTINCT) or \
               (target_distinct is not None and target_distinct > SANKEY_NODE_MAX_DISTINCT):
                continue

        try:
            validate_sql(chart["sql"], context=chart.get("chart_title", ""), expected_table=table_name)
            safe_charts.append(chart)
        except ValueError:
            pass

    parsed["charts"] = safe_charts
    return parsed

