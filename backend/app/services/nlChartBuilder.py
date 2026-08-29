import json
from app.services.llm import generate
from app.services.sqlGuard import validate_sql
from app.schemas.chartTypes import CHART_TYPE_GUIDANCE, CHART_TYPE_VALUES, CHART_TYPE_REGISTRY, ChartType
from app.services.chartValidation import missing_required_fields, apply_cardinality_guardrail


NL_CHART_PROMPT = """
You are a BI analyst building a single Metabase chart from a user's request.

Table: "{table_name}"

Available columns (name | base_type | semantic_role | chartable):
{field_reference}

{column_profile_section}

User request: {prompt}

HARD CONSTRAINTS — non-negotiable:
- Only use columns from the available columns list above
- Double-quote all column and table names
- PostgreSQL syntax only
- SELECT only — never emit DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- No semicolons
- aggregations: COUNT, SUM, AVG, or any valid PostgreSQL aggregate
- chart_type must match the SQL output shape and analytical intent:
{chart_type_guidance}

POSTGRESQL CAPABILITIES — use where appropriate:
- Window functions: RANK() OVER, SUM() OVER, AVG() OVER
- Date truncation: DATE_TRUNC('month', "date_col")
- Percentiles: PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "col")
- HAVING for post-aggregation filtering
- CTEs: WITH ... AS (...) SELECT ...
- CASE WHEN for conditional bucketing
- Top-N: ORDER BY ... LIMIT N
- ROUND("col"::numeric, 2) for decimal formatting

Return ONLY a JSON object with exactly these fields:
{{
  "chart_title": "string",
  "chart_type": "one of the valid chart types listed above",
  "sql": "SELECT ... (leave as empty string for chart types that don't require SQL, e.g. heatmap)"
  "x_alias": "exact column alias for the dimension, null for scalar/table/passthrough types",
  "y_alias": "exact column alias for the measure, null for scalar/table/passthrough types",
  "x_label": "optional — display axis title for x_alias, only if the alias itself is a poor label",
  "y_label": "optional — display axis title for y_alias, same rule as x_label",
  "series_alias": "optional — second dimension to group/stack by, only for bar/line/scatter/histogram",
  "source_alias": "optional — required for sankey only, exact alias of the source category column",
  "target_alias": "optional — required for sankey only, exact alias of the target category column",
  "value_alias": "optional — required for sankey only, exact alias of the count/weight column",
    "columns": "optional list of column name strings — only for heatmap, correlate just these numeric columns; omit for the full matrix across all numeric columns",
  "viz_params": "optional dict — required for gauge/funnel only, omit otherwise (including for sankey)",
  "reasoning": "one sentence explaining what this chart shows"
}}

Raw JSON only, no markdown.
"""


def _build_field_reference(field_map: dict, semantics: dict) -> str:
    role_map = {}
    for category in ("date_columns", "dimensions", "measures", "flags", "identifiers", "unknown"):
        for col in semantics.get(category, []):
            role_map[col["column"]] = {
                "semantic_role": col["semantic_role"],
                "chartable": col.get("chartable", True),
            }

    return "\n".join(
        f'  - "{col}" | {meta["base_type"]} | {role_map.get(col, {}).get("semantic_role", "unknown")} | chartable={role_map.get(col, {}).get("chartable", True)}'
        for col, meta in field_map.items()
    )


def _build_column_profile(selected_columns: list[str], profile: dict) -> str:
    lines = []
    for col in profile.get("columns", []):
        if col["column_name"] not in selected_columns:
            continue
        lines.append(f"  - {col['column_name']}:")
        if "stats" in col:
            lines.append(f"    stats: {col['stats']}")
        if "value_counts" in col:
            lines.append(f"    value_counts: {col['value_counts']}")
    return "\n".join(lines)


async def build_chart_from_prompt(
    prompt: str,
    field_map: dict,
    semantics: dict,
    table_name: str,
    selected_columns: list[str],
    profile: dict | None = None,
) -> dict:

    field_reference = _build_field_reference(field_map, semantics)

    if selected_columns and profile:
        col_profile = _build_column_profile(selected_columns, profile)
        column_profile_section = f"Column profile for referenced columns:\n{col_profile}" if col_profile else ""
    else:
        column_profile_section = ""

    prompt_text = NL_CHART_PROMPT.format(
        table_name=table_name,
        field_reference=field_reference,
        column_profile_section=column_profile_section,
        prompt=prompt,
        chart_type_guidance=CHART_TYPE_GUIDANCE,
    )

    raw = await generate(prompt_text, stage="nl_authoring")
    
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    chart = json.loads(raw)
    if chart.get("chart_type") not in CHART_TYPE_VALUES:
        raise ValueError(f"Unrecognised chart_type returned by NL chart builder: {chart.get('chart_type')!r}")

    is_nonSQL = not CHART_TYPE_REGISTRY[ChartType(chart["chart_type"])]["requires_sql"]

    required = ("chart_title", "chart_type") if is_nonSQL else ("chart_title", "chart_type", "sql")
    missing = missing_required_fields(chart, required)
    if missing:
        raise ValueError(f"NL chart builder response missing required field(s): {missing}")

    if not is_nonSQL:
        validate_sql(chart["sql"], context=chart.get("chart_title", ""), expected_table=table_name)
        violation = apply_cardinality_guardrail(chart, profile)
        if violation:
            raise ValueError(violation)
        
    return chart