import json
from app.services.llm import generate
from app.services.sqlGuard import validate_sql
from app.services.database import json_default


TURN1_PROMPT = """
You are a data analyst. Answer the user's question using the dataset context below.

Table: "{table_name}"

Available columns (name | base_type | semantic_role):
{field_reference}

Dataset profile (stats, value_counts, correlations):
{profile}

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
Write a PostgreSQL SELECT query against the table above.

HARD CONSTRAINTS:
- Only use columns from the available columns list
- Double-quote all column and table names
- PostgreSQL syntax only
- Boolean columns cannot be passed directly to SUM/AVG — cast first, e.g.
  SUM(CASE WHEN "flag_col" THEN 1 ELSE 0 END), never SUM("flag_col")
- SELECT only — no DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- No semicolons

Return:
{{
  "mode": "query",
  "sql": "SELECT ..."
}}

No markdown. Raw JSON only.
"""

TURN1_RETRY_PROMPT = """
You are a data analyst. Your previous PostgreSQL query failed.

Table: "{table_name}"

Available columns (name | base_type | semantic_role):
{field_reference}

User question: {prompt}

Previous SQL:
{sql}

Error:
{error}

Fix the query. Same hard constraints apply:
- Only use columns from the available columns list
- Double-quote all column and table names
- PostgreSQL syntax only
- Boolean columns cannot be passed directly to SUM/AVG — cast first, e.g.
  SUM(CASE WHEN "flag_col" THEN 1 ELSE 0 END), never SUM("flag_col")
- SELECT only — no DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE
- No semicolons

Return:
{{
  "mode": "query",
  "sql": "SELECT ..."
}}

No markdown. Raw JSON only.
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


def _build_field_reference(field_map: dict, semantics: dict) -> str:
    role_map = {}
    for category in ("date_columns", "dimensions", "measures", "flags", "identifiers", "unknown"):
        for col in semantics.get(category, []):
            role_map[col["column"]] = col["semantic_role"]

    return "\n".join(
        f'  - "{col}" | {meta["base_type"]} | {role_map.get(col, "unknown")}'
        for col, meta in field_map.items()
    )


async def _call_llm(prompt: str, stage: str = "insight") -> dict:
    raw = await generate(prompt, stage=stage)
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    return json.loads(raw)


async def generate_insights(
    table_name: str,
    field_map: dict,
    profile: dict,
    semantics: dict,
    prompt: str,
    execute_sql_fn,
) -> dict:

    field_reference = _build_field_reference(field_map, semantics)

    turn1 = TURN1_PROMPT.format(
        table_name=table_name,
        field_reference=field_reference,
        profile=json.dumps(profile, indent=2),
        prompt=prompt,
    )

    result = await _call_llm(turn1)

    if result.get("mode") == "query":
        sql = result["sql"]

        try:
            validate_sql(sql, table_name, context="insight query")
            query_results = await execute_sql_fn(sql)
        except Exception as e:
            # One retry: feed the error back and let the LLM fix the SQL,
            # same single-attempt-heal pattern as chart building. If this
            # also fails, surface a clean insight-shaped message instead
            # of letting the exception propagate as a 500.
            try:
                retry_prompt = TURN1_RETRY_PROMPT.format(
                    table_name=table_name,
                    field_reference=field_reference,
                    prompt=prompt,
                    sql=sql,
                    error=str(e),
                )
                retry_result = await _call_llm(retry_prompt)
                sql = retry_result["sql"]
                validate_sql(sql, context="insight query retry")
                query_results = await execute_sql_fn(sql)
            except Exception:
                return {
                    "mode": "stats",
                    "insights": [{
                        "title": "Couldn't answer this question",
                        "finding": "The query needed to answer this failed and couldn't be automatically fixed. Try rephrasing the question.",
                        "confidence": "low",
                    }],
                }

        turn2 = TURN2_PROMPT.format(
            prompt=prompt,
            query_results=json.dumps(query_results, indent=2, default=json_default),
        )
        result = await _call_llm(turn2, stage="insight_synthesis")

    return result