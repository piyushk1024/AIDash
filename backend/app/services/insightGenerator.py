import json
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _build_field_reference(field_map: dict) -> str:
    lines = []
    for col, meta in field_map.items():
        lines.append(f"  - {col} (base_type: {meta['base_type']})")
    return "\n".join(lines)


def _build_adhoc_mbql(intent: dict, table_id: int, database_id: int, field_map: dict) -> dict:
    """Convert Gemini's simple query intent into valid MBQL using field_map lookups."""

    query_clause = {"source-table": table_id}

    # SELECT fields
    if intent.get("select"):
        query_clause["fields"] = [
            ["field", field_map[col]["id"], {"base-type": field_map[col]["base_type"]}]
            for col in intent["select"]
            if col in field_map
        ]

    # AGGREGATION (count, sum, avg)
    if intent.get("aggregation"):
        agg = intent["aggregation"]
        agg_type = agg["type"]
        if agg_type == "count":
            query_clause["aggregation"] = [["count"]]
        elif agg_type in ("sum", "avg"):
            col = agg["column"]
            f = field_map[col]
            query_clause["aggregation"] = [[agg_type, ["field", f["id"], {"base-type": f["base_type"]}]]]

    # BREAKOUT (group by)
    if intent.get("breakout"):
        col = intent["breakout"]
        f = field_map[col]
        query_clause["breakout"] = [["field", f["id"], {"base-type": f["base_type"]}]]

    # FILTER
    if intent.get("filter"):
        fil = intent["filter"]
        col = fil["column"]
        f = field_map[col]
        field_ref = ["field", f["id"], {"base-type": f["base_type"]}]
        op = fil["operator"]
        if op == "not-null":
            query_clause["filter"] = ["not-null", field_ref]
        elif op == "=":
            query_clause["filter"] = ["=", field_ref, fil["value"]]
        elif op == "!=":
            query_clause["filter"] = ["!=", field_ref, fil["value"]]

    # ORDER BY
    if intent.get("order_by"):
        ob = intent["order_by"]
        col = ob["column"]
        f = field_map[col]
        direction = ob.get("direction", "desc")
        query_clause["order-by"] = [[direction, ["field", f["id"], {"base-type": f["base_type"]}]]]

    # LIMIT
    if intent.get("limit"):
        query_clause["limit"] = intent["limit"]

    return {
        "database": database_id,
        "type": "query",
        "query": query_clause
    }


TURN1_PROMPT = """
You are a data analyst. Answer the user's question using the dataset context below.

Dataset: {table_name}

Column semantics:
{semantics}

Dataset profile (stats, value_counts, correlations):
{profile}

Available columns:
{field_reference}

User question: {prompt}

---

Decide which mode to use:

MODE 1 — "stats": You can answer fully from the profile statistics above.
Return:
{{
  "mode": "stats",
  "insights": [
    {{"title": "...", "finding": "2-3 sentences grounded in the stats", "confidence": "high|medium|low"}}
  ]
}}

MODE 2 — "query": The question needs row-level data not in the profile.
Describe what to query using only column names from the available columns list.
Return:
{{
  "mode": "query",
  "intent": {{
    "select": ["col1", "col2"],
    "filter": {{"column": "col_name", "operator": "not-null"}},
    "order_by": {{"column": "col_name", "direction": "desc"}},
    "limit": 5
  }}
}}

For aggregation queries use:
{{
  "mode": "query",
  "intent": {{
    "aggregation": {{"type": "count"}},
    "breakout": "col_name",
    "order_by": {{"column": "col_name", "direction": "desc"}},
    "limit": 5
  }}
}}

Only use columns from the available columns list. No markdown. Raw JSON only.
"""

TURN2_PROMPT = """
You are a data analyst. The user asked: "{prompt}"

You ran a database query and got these results:
{query_results}

Generate insights from these results. Be specific, reference actual values.

Return ONLY:
{{
  "mode": "stats",
  "insights": [
    {{"title": "...", "finding": "2-3 sentences grounded in the results", "confidence": "high|medium|low"}}
  ]
}}

No markdown. Raw JSON only.
"""


def _call_gemini(prompt: str) -> dict:
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt
    )
    raw = response.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    return json.loads(raw)


def generate_insights(
    table_name: str,
    table_id: int,
    database_id: int,
    field_map: dict,
    profile: dict,
    semantics: dict,
    prompt: str,
    execute_mbql_fn
) -> dict:

    turn1 = TURN1_PROMPT.format(
        table_name=table_name,
        semantics=json.dumps(semantics, indent=2),
        profile=json.dumps(profile, indent=2),
        field_reference=_build_field_reference(field_map),
        prompt=prompt
    )

    result = _call_gemini(turn1)

    if result.get("mode") == "query":
        intent = result["intent"]
        mbql = _build_adhoc_mbql(intent, table_id, database_id, field_map)

        # print("=== BUILT MBQL ===")
        # print(json.dumps(mbql, indent=2))

        query_results = execute_mbql_fn(mbql)

        turn2 = TURN2_PROMPT.format(
            prompt=prompt,
            query_results=json.dumps(query_results, indent=2)
        )
        result = _call_gemini(turn2)

    return result