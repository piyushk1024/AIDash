import json
from app.services.llm import generate
from app.schemas.semantics import InferSemanticsResponse


def build_semantics_prompt(context: str, business_hint: str | None = None) -> str:
    hint_line = f"Business context: {business_hint}" if business_hint else ""
    return f"""
    You are a data analyst. Analyse the dataset below and classify every column.

    {hint_line}

    {context}

    Before classifying columns, reason through the following:
    - Use value_counts to understand categorical distributions and spot columns with mixed or heterogeneous meaning
    - Use grouped_stats to detect numeric columns that behave differently depending on another column's value (e.g. a margin column that means different things depending on a result type column). Flag these in your notes.
    - Use stats (mean, std, min, max) to understand numeric scale and detect outliers or summary rows
    - For numeric columns, use both distinct_count and the column name/values to determine if it is a flag, category, or measure:
    - If distinct_count is 2 and values are 0/1 or true/false → flag
    - If the column name suggests encoding (e.g. "status", "type", "category", "code") and distinct_count is low → dimension or flag
    - If the column name suggests ranking, scoring, or counting (e.g. "rank", "score", "rating", "orders", "count") → measure, even if distinct_count is low
    - If none of the above apply and distinct_count is 5 or fewer → flag or dimension, not measure
    - If a numeric column appears heterogeneous, reflect that in its semantic_role and add a note explaining the grouping
    - For any measure column identified as heterogeneous, set heterogeneous: true and set filter_column to the categorical column that controls its unit or meaning

    Return ONLY a JSON object with exactly these fields:
    - dataset_id: string
    - business_hint: string or null
    - dataset_grain: string (e.g. "daily per mall")
    - country: "IN", "US", or null — infer from column names, categorical
      values (city/state names, currency symbols, phone formats), or
      business_hint. Null if no confident signal exists. Do not guess.
    - date_columns: list of {{column, semantic_role, confidence, chartable}}
    - dimensions: list of {{column, semantic_role, confidence, chartable}}
    - measures: list of {{column, semantic_role, confidence, chartable, heterogeneous, filter_column}}
    - flags: list of {{column, semantic_role, confidence, chartable}}
    - identifiers: list of {{column, semantic_role, confidence, chartable}}
    - unknown: list of {{column, semantic_role, confidence, chartable}}
    - notes: list of strings

    Rules for chartable:
    - Set chartable: false for serial numbers, row IDs, and any column that is purely an identifier with no analytical value
    - Set chartable: false for name columns, description columns, and any free-text column regardless of distinct_count
    - Set chartable: true for all measures, flags, and date columns
    - Set chartable: true for categorical dimensions regardless of distinct_count — cardinality legibility is enforced per chart type at build time (see chartValidation.py), not at the semantics stage
    - Default to false when uncertain about a dimension's analytical value

    Confidence is a float between 0 and 1.
    Do not include any explanation or markdown. Return raw JSON only.
    """


async def infer_semantics_with_llm(
    dataset_profile: dict,
    business_hint: str | None = None,
) -> InferSemanticsResponse:
    context = f"Dataset profile:\n{json.dumps(dataset_profile, indent=2)}"
    prompt = build_semantics_prompt(context, business_hint)

    raw = await generate(prompt, stage="semantics")
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)
    parsed["dataset_id"] = dataset_profile["dataset_id"]
    parsed["business_hint"] = business_hint

    return InferSemanticsResponse(**parsed)