from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.database import (
    get_cached_semantics,
    get_dataset_metadata,
    get_cached_dashboard_plan,
    update_dashboard_plan,
    get_dataset_owner
)
from app.services.profiler import profile_csv
from app.services.nlChartBuilder import build_chart_from_prompt
from app.services.cardBuilder import build_card_with_healing
from app.dependencies import get_db, require_editor
from app.config import settings
from app.services.llm import LLMUnavailableError

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR


class NLChartRequest(BaseModel):
    prompt: str
    selected_columns: list[str] = []
    mode: str = "pipeline"


async def _fetch_profile_if_needed(dataset_id: str, selected_columns: list[str]) -> dict | None:
    if not selected_columns:
        return None
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found.")
    return profile_csv(matches[0], dataset_id)


async def _get_common_deps(db, dataset_id: str, user_id: str, mode: str) -> tuple:
    if mode not in ("pipeline", "agent"):
        raise HTTPException(status_code=400, detail="mode must be 'pipeline' or 'agent'")

    semantics = await get_cached_semantics(db, dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")

    owner = await get_dataset_owner(db, dataset_id)
    if owner != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    plan = await get_cached_dashboard_plan(db, dataset_id, mode=mode)
    if not plan:
        raise HTTPException(status_code=404, detail=f"No {mode} dashboard found. Build it first.")

    return semantics, metadata, plan


@router.post("/datasets/{dataset_id}/dashboard/charts")
async def add_nl_chart(
    dataset_id: str,
    body: NLChartRequest,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    semantics, metadata, plan = await _get_common_deps(db, dataset_id, current_user.user_id, body.mode)
    field_map = metadata["field_map"]
    table_name = metadata["table_name"]

    profile = await _fetch_profile_if_needed(dataset_id, body.selected_columns)
    try:
        chart_spec = await build_chart_from_prompt(
            prompt=body.prompt,
            field_map=field_map,
            semantics=semantics,
            table_name=table_name,
            selected_columns=body.selected_columns,
            profile=profile,
        )
    except LLMUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.")

    result, error = await build_card_with_healing(chart_spec, field_map, db)
    if error:
        raise HTTPException(status_code=500,
                            detail=f"Failed to create chart '{error.get('chart_title', 'unknown')}'",)

    updated_plan = {**plan, "charts": plan["charts"] + [result]}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return result


@router.put("/datasets/{dataset_id}/dashboard/charts/{card_id}")
async def edit_nl_chart(
    dataset_id: str,
    card_id: str,
    body: NLChartRequest,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    semantics, metadata, plan = await _get_common_deps(db, dataset_id, current_user.user_id, body.mode)
    field_map = metadata["field_map"]
    table_name = metadata["table_name"]

    profile = await _fetch_profile_if_needed(dataset_id, body.selected_columns)

    try:
        chart_spec = await build_chart_from_prompt(
            prompt=body.prompt,
            field_map=field_map,
            semantics=semantics,
            table_name=table_name,
            selected_columns=body.selected_columns,
            profile=profile,
        )
    except LLMUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.")

    result, error = await build_card_with_healing(chart_spec, field_map, db, existing_id=card_id)
    if error:
        raise HTTPException(status_code=500,
                            detail=f"Failed to create chart '{error.get('chart_title', 'unknown')}'",)

    updated_charts = [
        result if c.get("card_id") == card_id else c
        for c in plan["charts"]
    ]
    updated_plan = {**plan, "charts": updated_charts}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return result


@router.delete("/datasets/{dataset_id}/dashboard/charts/{card_id}")
async def delete_nl_chart(
    dataset_id: str,
    card_id: str,
    mode: str = "pipeline",
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    semantics, metadata, plan = await _get_common_deps(db, dataset_id, current_user.user_id, mode)

    updated_charts = [c for c in plan["charts"] if c.get("card_id") != card_id]
    updated_plan = {**plan, "charts": updated_charts}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return {"deleted": card_id}