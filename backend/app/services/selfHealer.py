import json
from app.services.llm import generate
from app.config import settings
from app.services.sqlGuard import validate_sql



HEAL_PROMPT = """
You are fixing a Metabase native SQL chart that failed.

Original chart:
{chart_spec}

Error returned by Metabase:
{error}

Available columns (name: base_type):
{field_reference}

Rules:
- Return a corrected version of the chart with the same JSON schema
- Rewrite the sql field to fix the error
- PostgreSQL syntax only
- Only use column names from the available columns list
- Double-quote all column and table names: "column_name", "table_name"
- SELECT only — never emit DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- chart_type must match the SQL output shape:
    - scalar: query must return exactly one row and one column
    - bar, line, pie: first column is dimension, second column is measure
- Return raw JSON only, no markdown

Corrected chart:
"""

def heal_chart_spec(chart: dict, error: str, field_map: dict) -> dict:
    field_reference = "\n".join(
        f"  - {col}: {meta['base_type']}"
        for col, meta in field_map.items()
    )

    prompt = HEAL_PROMPT.format(
        chart_spec=json.dumps(chart, indent=2),
        error=error,
        field_reference=field_reference
    )

    raw = generate(prompt)
    
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    
    healed = json.loads(raw)
    validate_sql(healed["sql"], context=healed.get("chart_title", ""))
    return healed