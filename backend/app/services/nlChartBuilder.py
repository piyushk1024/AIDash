# services/nlChartBuilder.py

import json
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

NL_CHART_PROMPT = """
You are a BI analyst building a single Metabase chart from a user's request.

Available columns (name: base_type, semantic_role, chartable):
{field_reference}

{column_profile_section}

User request: {prompt}

HARD CONSTRAINTS — non-negotiable:
- Only use columns where chartable is true
- Never use identifier columns as x_axis or y_axis
- Do not plan ratios, rates, or derived columns
- bar and line charts must have a non-null x_axis
- scalar charts must have x_axis null
- sum and avg aggregations require a non-null y_axis
- count aggregation must have y_axis null
- Only use column names that exist exactly as written above
- aggregations: count, sum, avg only
- chart types: bar, line, scalar, pie only

Return ONLY a JSON object with exactly these fields:
- chart_title: string
- chart_type: one of "line", "bar", "scalar", "pie"
- aggregation: one of "count", "sum", "avg"
- x_axis: column name or null
- y_axis: column name or null
- filters: empty list
- reasoning: one sentence explaining what this chart shows

No markdown. Raw JSON only.
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
        f"  - {col}: {meta['base_type']}, {role_map.get(col, {}).get('semantic_role', 'unknown')}, chartable={role_map.get(col, {}).get('chartable', True)}"
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


def build_chart_from_prompt(
    prompt: str,
    field_map: dict,
    semantics: dict,    
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
        field_reference=field_reference,
        column_profile_section=column_profile_section,
        prompt=prompt,
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt_text,
    )

    raw = response.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    return json.loads(raw)