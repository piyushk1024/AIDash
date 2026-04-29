import json
from google import genai
from app.schemas.semantics import InferSemanticsResponse
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def infer_semantics_with_llm(dataset_profile: dict, business_hint: str | None = None):
    
    hint_line = f"Business context: {business_hint}" if business_hint else ""
    
    prompt = f"""
    You are a data analyst. Analyse the dataset profile below and classify every column.

    {hint_line}

    Dataset profile:
    {json.dumps(dataset_profile, indent=2)}

    Before classifying columns, reason through the following:
    - Use value_counts to understand categorical distributions and spot columns with mixed or heterogeneous meaning
    - Use grouped_stats to detect numeric columns that behave differently depending on another column's value (e.g. a margin column that means different things depending on a result type column). Flag these in your notes.
    - Use stats (mean, std, min, max) to understand numeric scale and detect outliers or summary rows
    - If a numeric column appears heterogeneous, reflect that in its semantic_role and add a note explaining the grouping
    - For any measure column identified as heterogeneous, set heterogeneous: true and set filter_column to the categorical column that controls its unit or meaning    

    Return ONLY a JSON object with exactly these fields:
    - dataset_id: string
    - business_hint: string or null
    - dataset_grain: string (e.g. "daily per mall")
    - date_columns: list of {{column, semantic_role, confidence, chartable}}
    - dimensions: list of {{column, semantic_role, confidence, chartable}}
    - measures: list of {{column, semantic_role, confidence, chartable}}
    - flags: list of {{column, semantic_role, confidence, chartable}}
    - identifiers: list of {{column, semantic_role, confidence, chartable}}
    - unknown: list of {{column, semantic_role, confidence, chartable}}
    - notes: list of strings
    - measures: list of {{column, semantic_role, confidence, chartable, heterogeneous, filter_column}}

    Rules for chartable:
    - Set chartable: false for serial numbers, row IDs, and any column that is purely an identifier with no analytical value
    - Set chartable: false for columns with more than 50 distinct values where those values are not meaningful categories (e.g. free text, unique names)
    - Set chartable: true for all measures, flags, date columns, and meaningful categorical dimensions
    - Default to true when uncertain

    Confidence is a float between 0 and 1.
    Do not include any explanation or markdown. Return raw JSON only.
    """
    response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=prompt)

    # Strip markdown code fences if present
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    
    parsed = json.loads(raw)
    parsed = json.loads(raw)
    parsed["dataset_id"] = dataset_profile["dataset_id"]
    parsed["business_hint"] = business_hint

    return InferSemanticsResponse(**parsed)