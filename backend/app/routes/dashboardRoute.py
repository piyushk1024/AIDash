from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import get_db, require_editor
from app.services.database import (
    get_cached_semantics,
    get_cached_dashboard_plan,
    persist_dashboard_plan,
    update_dashboard_plan,
    is_plan_stale,
    get_dataset_metadata,
    get_dataset_owner,
    persist_profile_json
)
from app.services.dashboardPlanner import generate_dashboard_plan
from app.services.profiler import profile_csv
from app.services.cardBuilder import build_card_with_healing
from app.services.llm import is_llm_in_cooldown
from app.config import settings
from app.schemas.chartTypes import CHART_TYPE_VALUES
from app.services.llm import LLMUnavailableError
from starlette.concurrency import run_in_threadpool



router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

# VALID_CHART_TYPES = {"bar", "line", "scalar", "pie"}



def validate_and_clean_charts(charts: list) -> list:
    seen_titles = set()
    cleaned = []

    for chart in charts:
        # Must have required fields
        if not chart.get("sql") or not chart.get("chart_title") or not chart.get("chart_type"):
            continue

        # chart_type must be valid
        if chart["chart_type"] not in CHART_TYPE_VALUES:
            continue

        # Deduplicate on title
        if chart["chart_title"] in seen_titles:
            continue
        seen_titles.add(chart["chart_title"])

        cleaned.append(chart)

    return cleaned


@router.post("/generate-dashboard-plan/{dataset_id}")
@router.post("/generate-dashboard-plan/{dataset_id}")
async def generate_plan(dataset_id: str, db=Depends(get_db), current_user=Depends(require_editor)):

    owner = await get_dataset_owner(db, dataset_id)    
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    cached = await get_cached_dashboard_plan(db, dataset_id, mode="pipeline")
    stale = await is_plan_stale(db, dataset_id, mode="pipeline") if cached else False
    # print(f"STALE CHECK: cached={bool(cached)} stale={stale}")
    if cached and not stale:
        return cached

    semantics = await get_cached_semantics(db, dataset_id)
    if not semantics:
        raise HTTPException(
            status_code=404,
            detail="No semantics found for this dataset. Run inference first.",
        )

    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found")
    profile = await run_in_threadpool(profile_csv, matches[0], dataset_id)    
    await persist_profile_json(db, dataset_id, profile)

    metadata = await get_dataset_metadata(db, dataset_id)
    field_map = metadata["field_map"] if metadata else {}
    table_name = metadata["table_name"] if metadata else ""

    try:
        plan = await generate_dashboard_plan(dataset_id, semantics["semantics_json"], profile, table_name, field_map)
    except LLMUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.")

    plan["charts"] = validate_and_clean_charts(plan["charts"])

    if not plan["charts"]:
        raise HTTPException(
            status_code=500,
            detail="No valid charts could be generated. Try re-running semantics inference.",
        )

    plan["mode"] = "pipeline"
    await persist_dashboard_plan(db, dataset_id, plan)
    
    return plan

@router.post("/datasets/{dataset_id}/dashboard/build")
async def build_dashboard(
    dataset_id: str,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    plan = await get_cached_dashboard_plan(db, dataset_id, mode="pipeline")
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="No pipeline dashboard plan found. Run /generate-dashboard-plan first.",
        )

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No dataset metadata found. Re-upload the CSV to generate field mappings.",
        )
    field_map = metadata["field_map"]

    built_charts, errors = [], []
    provider_unavailable = False

    for chart in plan["charts"]:
        if provider_unavailable:
            errors.append({
                "chart_title": chart.get("chart_title"),
                "chart_type": chart.get("chart_type"),
                "failed": True,
                "skipped": True,
                "reason": "AI provider rate-limited — skipped, remaining charts not attempted. Retry shortly.",
            })
            continue

        result, error = await build_card_with_healing(
            chart, field_map, db, existing_id=chart.get("card_id"),
        )
        print("DEBUG error value:", error)
        
        if error:
            errors.append(error)
            if is_llm_in_cooldown():
                provider_unavailable = True
            continue
        
        # print("DEBUG chart keys:", list(chart.keys()))
        # print("DEBUG result keys:", list(result.keys()) if result else "result is None")

        # Persisted chart carries the union of the plan's chart definition
        # (x_alias/y_alias/series_alias/viz_params — needed to rebuild or
        # heal this chart again later) and the build result (card_id/rows/
        # spec/healed — needed to render it without rebuilding). Merging
        # onto `chart` rather than `result` keeps the plan fields even
        # though cardBuilder's return value never carried them.
        built_charts.append({**chart, **result})
    
    updated_plan = {**plan, "mode": "pipeline", "charts": built_charts, "errors": errors}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return {
        "cards_created": len(built_charts),
        "cards": built_charts,
        "errors": errors,
        "provider_unavailable": provider_unavailable,
    }