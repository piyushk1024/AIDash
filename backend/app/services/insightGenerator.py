import json
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def _build_field_reference(field_map: dict, semantics: dict) -> str:
    # Build a lookup of column -> semantic_role from semantics
    role_map = {}
    for category in (
        "date_columns",
        "dimensions",
        "measures",
        "flags",
        "identifiers",
        "unknown",
    ):
        for col in semantics.get(category, []):
            role_map[col["column"]] = col["semantic_role"]

    lines = []
    for col, meta in field_map.items():
        role = role_map.get(col, "unknown")
        lines.append(
            f"  - {col} (base_type: {meta['base_type']}, semantic_role: {role})"
        )
    return "\n".join(lines)


def _build_adhoc_mbql(
    intent: dict, table_id: int, database_id: int, field_map: dict
) -> dict:

    query_clause = {"source-table": table_id}

    # SELECT fields
    if intent.get("select"):
        fields = [
            ["field", field_map[col]["id"], {"base-type": field_map[col]["base_type"]}]
            for col in intent["select"]
            if col in field_map
        ]
        if fields:
            query_clause["fields"] = fields
        # if all selected columns missing from field_map, omit fields entirely

    # AGGREGATION (count, sum, avg)
    if intent.get("aggregation"):
        agg = intent["aggregation"]
        if isinstance(agg, list):
            agg = agg[0]
        agg_type = agg.get("type")
        if agg_type == "count":
            query_clause["aggregation"] = [["count"]]
        elif agg_type in ("sum", "avg"):
            col = agg.get("column")
            if col and col in field_map:
                f = field_map[col]
                if agg_type == "avg" and f["base_type"] == "type/Boolean":
                    raise ValueError(f"Cannot avg boolean column '{col}'")
                query_clause["aggregation"] = [
                    [agg_type, ["field", f["id"], {"base-type": f["base_type"]}]]
                ]

    # BREAKOUT (group by)
    if intent.get("breakout"):
        col = intent["breakout"]
        if isinstance(col, list):
            col = col[0]
        if col in field_map:
            f = field_map[col]
            query_clause["breakout"] = [
                ["field", f["id"], {"base-type": f["base_type"]}]
            ]
        # if column missing, skip breakout silently

    # FILTER
    if intent.get("filter"):
        fil = intent["filter"]
        if isinstance(fil, list):
            fil = fil[0]
        col = fil.get("column")
        if col and col in field_map:
            f = field_map[col]
            field_ref = ["field", f["id"], {"base-type": f["base_type"]}]
            op = fil.get("operator")
            if op == "not-null":
                query_clause["filter"] = ["not-null", field_ref]
            elif op in ("=", "!=", ">", "<", ">=", "<="):
                value = fil["value"]
                if f["base_type"] == "type/Boolean" and op in ("=", "!="):
                    value = bool(value)
                query_clause["filter"] = [op, field_ref, value]

    # ORDER BY
    if intent.get("order_by"):
        ob = intent["order_by"]
        if isinstance(ob, list):
            ob = ob[0]
        direction = ob.get("direction", "desc")
        if "aggregation" in query_clause:
            query_clause["order-by"] = [[direction, ["aggregation", 0]]]
        else:
            col = ob.get("column")
            if col and col in field_map:
                f = field_map[col]
                query_clause["order-by"] = [
                    [direction, ["field", f["id"], {"base-type": f["base_type"]}]]
                ]

    # LIMIT
    if intent.get("limit"):
        limit = intent["limit"]
        if isinstance(limit, int) and limit > 0:
            query_clause["limit"] = limit

    return {"database": database_id, "type": "query", "query": query_clause}


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
    "filter": {{"column": "col_name", "operator": "not-null|=|!=|>|<|>=|<=", "value": "filter_value"}},
    "order_by": {{"column": "col_name", "direction": "desc"}},
    "limit": 5
  }}
}}

For aggregation queries use:
{{
  "mode": "query",
  "intent": {{
    "aggregation": {{"type": "count|sum|avg", "column": "col_name"}},
    "breakout": "col_name",
    "filter": {{"column": "col_name", "operator": "not-null|=|!=|>|<|>=|<=", "value": "filter_value"}},
    "order_by": {{"column": "col_name", "direction": "desc"}},
    "limit": 5
  }}
}}

Rules:
- For "highest/lowest X per Y" questions, always use aggregation + breakout + order_by
- order_by direction should match the question — "highest" means "desc", "lowest" means "asc"
- filter value is required for all operators except "not-null"
- Only use columns from the available columns list. No markdown. Raw JSON only.
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
        # model="gemini-2.5-flash-lite",
        model="gemini-3.1-flash-lite",
        contents=prompt,
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
    execute_mbql_fn,
) -> dict:

    turn1 = TURN1_PROMPT.format(
        table_name=table_name,
        semantics=json.dumps(semantics, indent=2),
        profile=json.dumps(profile, indent=2),
        field_reference=_build_field_reference(field_map, semantics),
        prompt=prompt,
    )

    result = _call_gemini(turn1)

    if result.get("mode") == "query":

        intent = result["intent"]
        # print("=== INTENT ===")
        # print(json.dumps(intent, indent=2))

        mbql = _build_adhoc_mbql(intent, table_id, database_id, field_map)

        # print("=== BUILT MBQL ===")
        # print(json.dumps(mbql, indent=2))

        query_results = execute_mbql_fn(mbql)

        # query_results = execute_mbql_fn(mbql)

        turn2 = TURN2_PROMPT.format(
            prompt=prompt, query_results=json.dumps(query_results, indent=2)
        )
        result = _call_gemini(turn2)

    return result
