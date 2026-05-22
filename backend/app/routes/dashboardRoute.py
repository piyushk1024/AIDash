from fastapi import APIRouter, HTTPException
from app.services.database import (
    get_cached_semantics,
    get_cached_dashboard_plan,
    persist_dashboard_plan,
    get_dataset_metadata,
)
from app.services.dashboardPlanner import generate_dashboard_plan
from app.services.profiler import profile_csv
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

VALID_CHART_TYPES = {"bar", "line", "scalar", "pie"}


def validate_and_clean_charts(charts: list) -> list:
    seen_titles = set()
    cleaned = []

    for chart in charts:
        # Must have required fields
        if not chart.get("sql") or not chart.get("chart_title") or not chart.get("chart_type"):
            continue

        # chart_type must be valid
        if chart["chart_type"] not in VALID_CHART_TYPES:
            continue

        # Deduplicate on title
        if chart["chart_title"] in seen_titles:
            continue
        seen_titles.add(chart["chart_title"])

        cleaned.append(chart)

    return cleaned


@router.post("/generate-dashboard-plan/{dataset_id}")
async def generate_plan(dataset_id: str):

    cached = get_cached_dashboard_plan(dataset_id)
    if cached:
        return cached

    semantics = get_cached_semantics(dataset_id)
    if not semantics:
        raise HTTPException(
            status_code=404,
            detail="No semantics found for this dataset. Run inference first.",
        )

    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found")
    profile = profile_csv(matches[0], dataset_id)

    metadata = get_dataset_metadata(dataset_id)
    field_map = metadata["field_map"] if metadata else {}
    table_name = metadata["table_name"] if metadata else ""

    plan = generate_dashboard_plan(dataset_id, semantics, profile, table_name, field_map)

    plan["charts"] = validate_and_clean_charts(plan["charts"])

    if not plan["charts"]:
        raise HTTPException(
            status_code=500,
            detail="No valid charts could be generated. Try re-running semantics inference.",
        )

    persist_dashboard_plan(dataset_id, plan)
    return plan