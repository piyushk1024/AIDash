# app/routes/agentRoute.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.database import (
    get_cached_semantics,
    get_dataset_metadata,
    get_dataset_owner,
    persist_metabase_dashboard_id,
    persist_dashboard_plan,
)
from app.services.profiler import profile_csv
from app.services.agentOrchestrator import run_agent
from app.services.metabaseClient import (
    get_session_token,
    get_database_id,
    create_dashboard,
    create_public_link,
)
from app.dependencies import get_db, get_http_client, get_app_state, require_editor
from app.config import settings

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR

DEFAULT_GOAL = "Build the most analytically interesting dashboard you can from this dataset."


class AgentRequest(BaseModel):
    goal: str = DEFAULT_GOAL


@router.post("/datasets/{dataset_id}/dashboard/agent")
async def run_agent_dashboard(
    dataset_id: str,
    body: AgentRequest,
    db=Depends(get_db),
    http_client=Depends(get_http_client),
    app_state=Depends(get_app_state),
    current_user=Depends(require_editor),
):
    semantics = await get_cached_semantics(db, dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")

    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found.")
    profile = profile_csv(matches[0], dataset_id)

    token = await get_session_token(http_client, app_state)
    database_id = await get_database_id(token, http_client)

    dashboard_title = f"{metadata['table_name']} — Agent"
    dashboard_id = await create_dashboard(token, http_client, dashboard_title)
    public_url = await create_public_link(token, http_client, dashboard_id)
    await persist_metabase_dashboard_id(db, dataset_id, dashboard_id, public_url)

    goal = body.goal.strip() or DEFAULT_GOAL

    result = await run_agent(
        goal=goal,
        table_name=metadata["table_name"],
        field_map=metadata["field_map"],
        semantics=semantics,
        profile=profile,
        dashboard_id=dashboard_id,
        token=token,
        http_client=http_client,
        database_id=database_id,
    )

    agent_plan = {
        "dataset_id": dataset_id,
        "dashboard_title": dashboard_title,
        "mode": "agent",
        "goal": goal,
        "charts": result["charts_built"],
    }
    await persist_dashboard_plan(db, dataset_id, agent_plan)

    return {
        "dashboard_id": dashboard_id,
        "public_url": public_url,
        "charts_built": result["charts_built"],
        "trace": result["trace"],
    }