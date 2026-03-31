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

Return ONLY a JSON object with exactly these fields:
- dataset_id: string
- business_hint: string or null
- dataset_grain: string (e.g. "daily per mall")
- date_columns: list of {{column, semantic_role, confidence}}
- dimensions: list of {{column, semantic_role, confidence}}
- measures: list of {{column, semantic_role, confidence}}
- flags: list of {{column, semantic_role, confidence}}
- identifiers: list of {{column, semantic_role, confidence}}
- unknown: list of {{column, semantic_role, confidence}}
- notes: list of strings

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

    # Debug: print raw to see what Gemini actually returned
    # print("RAW RESPONSE:", raw)

    parsed = json.loads(raw)
    parsed = json.loads(raw)
    parsed["dataset_id"] = dataset_profile["dataset_id"]
    parsed["business_hint"] = business_hint

    return InferSemanticsResponse(**parsed)