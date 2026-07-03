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
from app.services.cardBuilder import create_card_with_healing
from app.services.metabaseClient import (
    get_session_token,
    get_database_id,
    add_card_to_dashboard,
    get_dashboard_card_ids,
    delete_card,
)
from app.dependencies import get_db, get_http_client, get_app_state, require_editor
from app.config import settings
from app.services.llm import LLMUnavailableError

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR


class NLChartRequest(BaseModel):
    prompt: str
    selected_columns: list[str] = []


async def _fetch_profile_if_needed(dataset_id: str, selected_columns: list[str]) -> dict | None:
    if not selected_columns:
        return None
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found.")
    return profile_csv(matches[0], dataset_id)


async def _get_common_deps(db, dataset_id: str, user_id: str) -> tuple:
    semantics = await get_cached_semantics(db, dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")
    
    owner = await get_dataset_owner(db, dataset_id)
    if owner != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    dashboard_id = metadata.get("metabase_dashboard_id")
    if not dashboard_id:
        raise HTTPException(status_code=404, detail="No dashboard found. Build dashboard first.")

    plan = await get_cached_dashboard_plan(db, dataset_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No dashboard plan found.")

    return semantics, metadata, dashboard_id, plan


@router.post("/datasets/{dataset_id}/dashboard/charts")
async def add_nl_chart(
    dataset_id: str,
    body: NLChartRequest,
    db=Depends(get_db),
    http_client=Depends(get_http_client),
    app_state=Depends(get_app_state),
    current_user=Depends(require_editor),
):
    semantics, metadata, dashboard_id, plan = await _get_common_deps(db, dataset_id, current_user.user_id)
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

    token = await get_session_token(http_client, app_state)
    database_id = await get_database_id(token, http_client)
    position = len(await get_dashboard_card_ids(token, http_client, dashboard_id))

    result, error = await create_card_with_healing(token, http_client, chart_spec, field_map, database_id)
    if error:
        raise HTTPException(status_code=500,
                            detail=f"Failed to create chart '{error.get('chart_title', 'unknown')}'",)
    await add_card_to_dashboard(token, http_client, dashboard_id, result["card_id"], position)

    new_chart_entry = {**chart_spec, "card_id": result["card_id"]}
    updated_plan = {**plan, "charts": plan["charts"] + [new_chart_entry]}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return result


@router.put("/datasets/{dataset_id}/dashboard/charts/{card_id}")
async def edit_nl_chart(
    dataset_id: str,
    card_id: int,
    body: NLChartRequest,
    db=Depends(get_db),
    http_client=Depends(get_http_client),
    app_state=Depends(get_app_state),
    current_user=Depends(require_editor),
):
    semantics, metadata, dashboard_id, plan = await _get_common_deps(db, dataset_id, current_user.user_id)
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

    token = await get_session_token(http_client, app_state)
    database_id = await get_database_id(token, http_client)

    await delete_card(token, http_client, card_id)
    position = len(await get_dashboard_card_ids(token, http_client, dashboard_id))

    result, error = await create_card_with_healing(token, http_client, chart_spec, field_map, database_id)
    if error:
        raise HTTPException(status_code=500,
                            detail=f"Failed to create chart '{error.get('chart_title', 'unknown')}'",)

    await add_card_to_dashboard(token, http_client, dashboard_id, result["card_id"], position)

    updated_charts = [
        {**chart_spec, "card_id": result["card_id"]}
        if c.get("card_id") == card_id
        else c
        for c in plan["charts"]
    ]
    updated_plan = {**plan, "charts": updated_charts}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return result


@router.delete("/datasets/{dataset_id}/dashboard/charts/{card_id}")
async def delete_nl_chart(
    dataset_id: str,
    card_id: int,
    db=Depends(get_db),
    http_client=Depends(get_http_client),
    app_state=Depends(get_app_state),
    current_user=Depends(require_editor),
):
    semantics, metadata, dashboard_id, plan = await _get_common_deps(db, dataset_id, current_user.user_id)

    token = await get_session_token(http_client, app_state)
    await delete_card(token, http_client, card_id)

    updated_charts = [c for c in plan["charts"] if c.get("card_id") != card_id]
    updated_plan = {**plan, "charts": updated_charts}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return {"deleted": card_id}