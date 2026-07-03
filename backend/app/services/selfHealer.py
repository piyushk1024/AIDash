import json
from app.services.llm import generate
from app.config import settings
from app.services.sqlGuard import validate_sql
from app.schemas.chartTypes import CHART_TYPE_GUIDANCE, CHART_TYPE_VALUES



HEAL_PROMPT = """
You are fixing a Metabase chart that failed.

Original chart:
{chart_spec}

Error returned by Metabase:
{error}

Available columns (name: base_type):
{field_reference}

Rules:
- Return a corrected version of the chart with the same JSON schema
- If the error is about the SQL (syntax, unknown column, aggregation mismatch),
  rewrite the sql field to fix it
- If the error is about visualization/display configuration and the chart has a
  viz_params field, fix viz_params instead — the shape it needs depends on
  chart_type (see guidance below). Do not touch sql for a pure viz_params error.
- PostgreSQL syntax only
- Only use column names from the available columns list
- Double-quote all column and table names: "column_name", "table_name"
- SELECT only — never emit DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- chart_type must match the SQL output shape and stay one of the valid types:
{chart_type_guidance}
- Return raw JSON only, no markdown

Corrected chart:
"""

async def heal_chart_spec(chart: dict, error: str, field_map: dict) -> dict:
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

    raw = await generate(prompt, stage="healer" )
    
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    
    healed = json.loads(raw)

    if healed.get("chart_type") not in CHART_TYPE_VALUES:
        raise ValueError(f"Healer returned an invalid chart_type: {healed.get('chart_type')!r}")

    validate_sql(healed["sql"], context=healed.get("chart_title", ""))
    return healed