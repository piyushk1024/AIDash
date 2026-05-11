from fastapi import APIRouter, HTTPException
from app.services.database import (
    get_cached_semantics,
    get_cached_dashboard_plan,
    persist_dashboard_plan
)
from app.services.dashboardPlanner import generate_dashboard_plan
from app.services.profiler import profile_csv
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

VALID_AGGREGATIONS = {"count", "sum", "avg"}
VALID_CHART_TYPES = {"bar", "line", "scalar", "pie"}

def validate_and_clean_charts(charts: list, field_map: dict) -> list:
    seen = set()
    cleaned = []

    for chart in charts:
        chart_type = chart.get("chart_type")
        aggregation = chart.get("aggregation")
        x_axis = chart.get("x_axis")
        y_axis = chart.get("y_axis")

        # Basic type and aggregation validity
        if chart_type not in VALID_CHART_TYPES:
            continue
        if aggregation not in VALID_AGGREGATIONS:
            continue

        # Structural rules
        if aggregation == "count" and y_axis is not None:
            chart["y_axis"] = None
            y_axis = None
        if aggregation == "avg" and y_axis:
            y_field = field_map.get(y_axis, {})
            if y_field.get("base_type") == "type/Boolean":
                continue
        if chart_type == "scalar" and x_axis is not None:
            chart["x_axis"] = None
            x_axis = None
        if chart_type in ("bar", "line", "pie") and not x_axis:
            continue

        # Column existence check against field_map
        if x_axis and x_axis not in field_map:
            continue
        if y_axis and y_axis not in field_map:
            continue

        # Deduplication
        key = (x_axis, y_axis, aggregation)
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(chart)

    return cleaned


@router.post("/generate-dashboard-plan/{dataset_id}")
async def generate_plan(dataset_id: str):

    # Check for cached plan first
    cached = get_cached_dashboard_plan(dataset_id)
    if cached:
        return cached

    # Load persisted semantics
    semantics = get_cached_semantics(dataset_id)
    if not semantics:
        raise HTTPException(
            status_code=404,
            detail="No semantics found for this dataset. Run inference first."
        )

    # Load profile
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found")
    profile = profile_csv(matches[0], dataset_id)

    # Load field map for validation
    from app.services.database import get_dataset_metadata
    metadata = get_dataset_metadata(dataset_id)
    field_map = metadata["field_map"] if metadata else {}

    # Generate plan
    plan = generate_dashboard_plan(dataset_id, semantics, profile)

    # Validate and clean charts
    plan["charts"] = validate_and_clean_charts(plan["charts"], field_map)

    if not plan["charts"]:
        raise HTTPException(
            status_code=500,
            detail="No valid charts could be generated. Try re-running semantics inference."
        )

    # Persist and return
    persist_dashboard_plan(dataset_id, plan)
    return plan