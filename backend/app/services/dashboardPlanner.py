import json
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def generate_dashboard_plan(dataset_id: str, semantics: dict) -> dict:
    
    prompt = f"""
You are a BI analyst. Given the semantic profile of a dataset, recommend a set of dashboard charts.

Dataset semantics:
{json.dumps(semantics, indent=2)}

Return ONLY a JSON object with exactly these fields:
- dataset_id: string
- dashboard_title: string
- charts: list of objects, each with:
    - chart_id: a short unique slug (e.g. "footfall-by-date")
    - chart_title: string
    - chart_type: one of "line", "bar", "scalar", "pie"
    - x_axis: column name or null
    - y_axis: column name or null
    - group_by: column name or null
    - filters: empty list for now
    - reasoning: one sentence explaining why this chart is useful

Aim for 5 to 8 charts. Prioritise measures over time, dimensions as group_by, and scalar KPIs for key measures.
Do not include markdown. Return raw JSON only.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )
    
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)
    parsed["dataset_id"] = dataset_id
    return parsed