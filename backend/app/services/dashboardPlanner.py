import json
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def generate_dashboard_plan(dataset_id: str, semantics: dict, profile: dict) -> dict:

    prompt = f"""
You are a BI analyst planning a Metabase dashboard. You will reason in two passes before producing output.

Dataset semantics:
{json.dumps(semantics, indent=2)}

Dataset profile (stats, value_counts, correlations, grouped_stats):
{json.dumps(profile, indent=2)}

---

PASS 1 — Questions:
Identify the 4 to 6 most interesting analytical questions this dataset can answer. Think about:
- What are the highest and lowest performing entities?
- Are there distributions that reveal imbalance or skew?
- Are there correlations between columns worth surfacing?
- Are there trends over time if date columns exist?
- Are there heterogeneous numeric columns that need to be broken out by a categorical?
- What would a domain expert want to know first?

PASS 2 — Charts:
For each question from Pass 1, plan one chart that answers it directly.

---

HARD CONSTRAINTS — these are non-negotiable:
- Only use columns where chartable is true
- Never use identifier or serial number columns as x_axis or y_axis
- No two charts may share the same (x_axis, y_axis, aggregation) combination
- Do not plan ratios, rates, or derived columns — Metabase cannot compute them
- Do not plan top-N charts — Metabase cannot filter to top N in basic query mode
- bar and line charts must have a non-null x_axis
- scalar charts must have x_axis null
- sum and avg aggregations require a non-null y_axis
- count aggregation must have y_axis null
- Only use column names that exist exactly as written in the semantics

METABASE CAPABILITIES — only these are supported:
- aggregations: count, sum, avg
- chart types: bar, line, scalar, pie
- one x_axis column, one y_axis column, no multi-series

---

Return ONLY a JSON object with exactly these fields:
- dataset_id: string
- dashboard_title: string
- charts: list of objects, each with:
    - chart_id: short unique slug
    - chart_title: string
    - chart_type: one of "line", "bar", "scalar", "pie"
    - aggregation: one of "count", "sum", "avg"
    - x_axis: column name or null
    - y_axis: column name or null
    - filters: empty list
    - reasoning: one sentence tying this chart back to a specific analytical question

Aim for 5 to 7 charts. Do not include markdown. Return raw JSON only.
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