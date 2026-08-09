import json
from app.services.llm import generate
from app.services.sqlGuard import validate_sql
from app.schemas.chartTypes import CHART_TYPE_GUIDANCE, CHART_TYPE_VALUES



HEAL_PROMPT = """
You are fixing a chart that failed to build.

Original chart:
{chart_spec}

Error:
{error}

Available columns in the source table (name: base_type):
{field_reference}

Rules — match the error to exactly one case below:
- SQL execution error (syntax, unknown column, aggregation mismatch) or a
  rejected-SQL error (must start with SELECT/WITH, disallowed keyword):
  rewrite the sql field to fix it.
- "Query returned no rows": the SQL's WHERE/JOIN/filter conditions are
  likely too restrictive or reference incorrect values — broaden or correct
  them using the available columns, or reconsider the chart's premise
  entirely if the filter looks fundamentally wrong.
- "x_alias/y_alias required": set x_alias to the column alias used for the
  dimension/category in the SQL's SELECT list, and y_alias to the column
  alias used for the measure/aggregate value — matching exactly what the
  SQL actually returns as column names.
- "Column '...' not found in query results" (lists the columns that ARE
  available): the chart's x_alias/y_alias/series_alias values don't match
  what the SQL actually returns. Fix this by updating the x_alias/y_alias/
  series_alias field VALUES to reference one of the listed available
  columns. Do not rename SQL column aliases to the literal words
  "x_alias", "y_alias", or "series_alias" — those are JSON field names,
  not meaningful column names. If you do need to rename a SQL alias
  instead, give it a real, descriptive name reflecting the data (e.g.
  "error_count", "environment"), never the field name itself.  
- "viz_params required" or an error about visualization/display
  configuration: add or fix the viz_params field — the shape it needs
  depends on chart_type (see guidance below). Do not touch sql for a pure
  viz_params error.
- If chart_type itself looks wrong or unrecognized, replace it with the
  correct one of the valid types below, matching the SQL's actual output
  shape.

General constraints:
- Return a corrected version of the chart with the same JSON schema
- PostgreSQL syntax only
- Only use column names from the available columns list
- Double-quote all column and table names: "column_name", "table_name"
- SELECT only — never emit DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- chart_type must be one of the valid types:
{chart_type_guidance}
- Return raw JSON only, no markdown

Corrected chart:
"""

async def heal_chart_spec(chart: dict, error: str, field_map: dict, table_name: str) -> dict:
    field_reference = "\n".join(
        f"  - {col}: {meta['base_type']}"
        for col, meta in field_map.items()
    )

    prompt = HEAL_PROMPT.format(
        chart_spec=json.dumps(chart, indent=2),
        error=error,
        field_reference=field_reference,
        chart_type_guidance=CHART_TYPE_GUIDANCE,
    )

    raw = await generate(prompt, stage="healer")
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    healed = json.loads(raw)
    healed = {**chart, **healed}

    validate_sql(healed["sql"], table_name, context=healed.get("chart_title", ""))
    if healed.get("chart_type") not in CHART_TYPE_VALUES:
        raise ValueError(f"Healed chart_type '{healed.get('chart_type')}' is not a valid chart type")

    return healed