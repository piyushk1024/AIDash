import json
from app.schemas.semantics import InferSemanticsResponse


def infer_semantics_with_llm(dataset_profile: dict, business_hint: str | None = None):
    # Placeholder until you wire a real LLM
    # Replace this block with your provider call

    prompt = {
        "business_hint": business_hint,
        "dataset_profile": dataset_profile,
        "task": (
            "Classify columns into date_columns, dimensions, measures, flags, "
            "identifiers, unknown. Infer dataset_grain. Return strict JSON only."
        ),
    }

    # TEMP FAKE OUTPUT FOR TESTING
    fake = {
        "dataset_id": dataset_profile["dataset_id"],
        "business_hint": business_hint,
        "dataset_grain": "daily per mall",
        "date_columns": [
            {"column": "date", "semantic_role": "event_date", "confidence": 0.98}
        ],
        "dimensions": [
            {"column": "mall_name", "semantic_role": "location", "confidence": 0.96},
            {"column": "city", "semantic_role": "geography", "confidence": 0.90},
            {"column": "zone", "semantic_role": "region", "confidence": 0.88},
            {
                "column": "weather_tag",
                "semantic_role": "environment",
                "confidence": 0.82,
            },
        ],
        "measures": [
            {
                "column": "footfall",
                "semantic_role": "traffic_count",
                "confidence": 0.97,
            },
            {
                "column": "sales_amount_inr",
                "semantic_role": "revenue",
                "confidence": 0.95,
            },
            {
                "column": "occupancy_rate_pct",
                "semantic_role": "occupancy_rate",
                "confidence": 0.93,
            },
            {
                "column": "maintenance_tickets",
                "semantic_role": "ticket_count",
                "confidence": 0.92,
            },
        ],
        "flags": [
            {
                "column": "promo_event_flag",
                "semantic_role": "promotion_flag",
                "confidence": 0.91,
            },
            {
                "column": "holiday_flag",
                "semantic_role": "holiday_flag",
                "confidence": 0.94,
            },
            {
                "column": "is_weekend",
                "semantic_role": "weekend_flag",
                "confidence": 0.95,
            },
        ],
        "identifiers": [],
        "unknown": [],
        "notes": ["Likely daily operational dataset for mall performance tracking"],
    }

    return InferSemanticsResponse(**fake)
