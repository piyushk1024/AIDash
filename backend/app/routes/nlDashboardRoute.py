# routes/nlDashboardRoute.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.database import (
    get_cached_semantics,
    get_dataset_metadata,
    get_cached_dashboard_plan,
    update_dashboard_plan,
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
from app.config import settings

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR


class NLChartRequest(BaseModel):
    prompt: str
    selected_columns: list[str] = []


def _fetch_profile_if_needed(dataset_id: str, selected_columns: list[str]) -> dict | None:
    if not selected_columns:
        return None
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found.")
    return profile_csv(matches[0], dataset_id)


def _get_common_deps(dataset_id: str) -> tuple:
    semantics = get_cached_semantics(dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")

    metadata = get_dataset_metadata(dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    dashboard_id = metadata.get("metabase_dashboard_id")
    if not dashboard_id:
        raise HTTPException(status_code=404, detail="No dashboard found. Build dashboard first.")

    plan = get_cached_dashboard_plan(dataset_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No dashboard plan found.")

    return semantics, metadata, dashboard_id, plan


# ── Ask: NL → new chart → append to dashboard ──────────────────

@router.post("/datasets/{dataset_id}/dashboard/charts")
async def add_nl_chart(dataset_id: str, body: NLChartRequest):

    semantics, metadata, dashboard_id, plan = _get_common_deps(dataset_id)
    field_map = metadata["field_map"]
    table_id = metadata["metabase_table_id"]

    profile = _fetch_profile_if_needed(dataset_id, body.selected_columns)

    chart_spec = build_chart_from_prompt(
        prompt=body.prompt,
        field_map=field_map,
        semantics=semantics,
        selected_columns=body.selected_columns,
        profile=profile,
    )

    token = get_session_token()
    database_id = get_database_id(token)
    position = len(get_dashboard_card_ids(token, dashboard_id))

    result, error = create_card_with_healing(token, chart_spec, table_id, field_map, database_id)
    if error:
        raise HTTPException(status_code=500, detail=error)

    add_card_to_dashboard(token, dashboard_id, result["card_id"], position)

    # Append to plan so rebuild includes this card
    new_chart_entry = {**chart_spec, "card_id": result["card_id"]}
    updated_plan = {**plan, "charts": plan["charts"] + [new_chart_entry]}
    update_dashboard_plan(dataset_id, updated_plan)

    return result


# ── Edit: NL instruction → update existing card ─────────────────

@router.put("/datasets/{dataset_id}/dashboard/charts/{card_id}")
async def edit_nl_chart(dataset_id: str, card_id: int, body: NLChartRequest):

    semantics, metadata, dashboard_id, plan = _get_common_deps(dataset_id)
    field_map = metadata["field_map"]
    table_id = metadata["metabase_table_id"]

    profile = _fetch_profile_if_needed(dataset_id, body.selected_columns)

    chart_spec = build_chart_from_prompt(
        prompt=body.prompt,
        field_map=field_map,
        semantics=semantics,
        selected_columns=body.selected_columns,
        profile=profile,
    )

    token = get_session_token()
    database_id = get_database_id(token)

    delete_card(token, card_id)
    position = len(get_dashboard_card_ids(token, dashboard_id))

    result, error = create_card_with_healing(token, chart_spec, table_id, field_map, database_id)
    if error:
        raise HTTPException(status_code=500, detail=error)

    add_card_to_dashboard(token, dashboard_id, result["card_id"], position)

    # Swap old card entry in plan with updated spec + new card_id
    updated_charts = [
        {**chart_spec, "card_id": result["card_id"]}
        if c.get("card_id") == card_id
        else c
        for c in plan["charts"]
    ]
    updated_plan = {**plan, "charts": updated_charts}
    update_dashboard_plan(dataset_id, updated_plan)

    return result

#----------Delete card functionality---------
@router.delete("/datasets/{dataset_id}/dashboard/charts/{card_id}")
async def delete_nl_chart(dataset_id: str, card_id: int):
    semantics, metadata, dashboard_id, plan = _get_common_deps(dataset_id)

    token = get_session_token()
    delete_card(token, card_id)

    updated_charts = [c for c in plan["charts"] if c.get("card_id") != card_id]
    updated_plan = {**plan, "charts": updated_charts}
    update_dashboard_plan(dataset_id, updated_plan)

    return {"deleted": card_id}