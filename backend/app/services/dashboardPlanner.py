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
        - chart_id: a short unique slug (e.g. "matches-by-season")
        - chart_title: string
        - chart_type: one of "line", "bar", "scalar", "pie"
        - aggregation: one of "count", "sum", "avg" — choose based on chart intent
        - x_axis: column name for grouping/breakdown. Required for bar, line, pie. For scalar, use null.
        - y_axis: column name to aggregate. Required for sum and avg. For count, use null.
        - filters: empty list for now
        - reasoning: one sentence explaining why this chart is useful
    When selecting charts, go beyond simple counts and averages. Look for:
    - Records and extremes (highest, lowest, most frequent values)
    - Relationships between two columns that might reveal a pattern or correlation
    - Distributions that reveal imbalance or skew
    - Rankings (top N by a measure)
    - Trends that show change over time
    - Ratios or rates that are more meaningful than raw counts
    Avoid obvious filler charts like simple row counts unless they serve as a genuine KPI.

    Rules:
    - Use aggregation "count" when counting rows (e.g. number of matches). Set y_axis to null for count charts.
    - Use aggregation "sum" or "avg" when measuring a numeric column.
    - scalar charts must have x_axis null and y_axis null or a single numeric column.
    - Never invent column names. Only use column names present in the dataset semantics.

    Aim for 5 to 8 charts. Do not include markdown. Return raw JSON only.
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