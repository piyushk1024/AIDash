import json
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

HEAL_PROMPT = """
You are fixing a Metabase chart spec that failed to create.

Original chart spec:
{chart_spec}

Error returned by Metabase:
{error}

Available columns (name: base_type):
{field_reference}

Rules:
- Return a corrected version of the chart spec with the same JSON schema
- Only use column names from the available columns list
- aggregations: count, sum, avg only
- chart types: bar, line, scalar, pie only
- count must have y_axis null
- sum and avg require a non-null y_axis
- scalar must have x_axis null
- bar, line, pie must have a non-null x_axis
- Do not invent new columns or aggregation types
- Return raw JSON only, no markdown

Corrected chart spec:
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

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )

    raw = response.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    return json.loads(raw)