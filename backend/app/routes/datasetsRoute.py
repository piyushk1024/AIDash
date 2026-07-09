from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.dependencies import get_current_user, get_db
from app.services.database import (
    get_dataset_state,
    get_dataset_owner,
    get_dataset_metadata,
    get_cached_dashboard_plan,
    get_published_dashboard,
    set_published,
)
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

@router.get("/datasets/{dataset_id}/state")
async def get_state(dataset_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    state = await get_dataset_state(db, dataset_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dataset not found")
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = state["metadata"]

    # Reconstruct uploadResult in the same shape the frontend expects
    # so rehydration requires no special casing
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    original_filename = matches[0].name.split("_", 1)[1] if matches else metadata["table_name"]

    upload_result = {
        "dataset_id": dataset_id,
        "original_filename": original_filename,
        "table_name": metadata["table_name"],
        "row_count": None,   # not stored — acceptable for rehydration
        "field_map": metadata["field_map"],
    }

    # Pipeline and agent dashboards now coexist independently — both are
    # reconstructed here if present, rather than picking one via a shared
    # dashboard id. published/published_mode gate which one (if any) is
    # publicly visible, not which one exists.
    pipeline_plan = state["pipeline_plan"]
    agent_plan = state["agent_plan"]

    dashboard_result = None
    if pipeline_plan and pipeline_plan.get("charts"):
        dashboard_result = {
            "published":     metadata.get("published", False) and metadata.get("published_mode") == "pipeline",
            "cards_created": len(pipeline_plan.get("charts", [])),
            "cards": [
                {
                    "card_id":        c.get("card_id"),
                    "chart_title":    c["chart_title"],
                    "chart_type":     c.get("chart_type"),
                    "healed":         c.get("healed", False),
                    "original_chart": c.get("original_chart"),
                    "healed_chart":   c.get("healed_chart"),
                }
                for c in pipeline_plan.get("charts", [])
            ],
            "errors": pipeline_plan.get("errors", []),
        }

    agent_result = None
    if agent_plan and agent_plan.get("charts"):
        agent_result = {
            "published":    metadata.get("published", False) and metadata.get("published_mode") == "agent",
            "charts_built": agent_plan.get("charts", []),
            "trace":        agent_plan.get("trace", []),
        }

    return {
        "upload_result":    upload_result,
        "semantics":        state["semantics"],
        "pipeline_plan":    pipeline_plan,
        "agent_plan":       agent_plan,
        "dashboard_result": dashboard_result,
        "agent_result":     agent_result,
    }


class PublishRequest(BaseModel):
    mode: str = "pipeline"


@router.post("/datasets/{dataset_id}/publish")
async def publish_dashboard(
    dataset_id: str,
    body: PublishRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner = await get_dataset_owner(db, dataset_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if body.mode not in ("pipeline", "agent"):
        raise HTTPException(status_code=400, detail="mode must be 'pipeline' or 'agent'")

    plan = await get_cached_dashboard_plan(db, dataset_id, mode=body.mode)
    if not plan or not plan.get("charts"):
        raise HTTPException(status_code=400, detail=f"Build the {body.mode} dashboard before publishing")

    metadata = await get_dataset_metadata(db, dataset_id)
    currently_published = metadata.get("published", False) and metadata.get("published_mode") == body.mode
    new_state = not currently_published
    await set_published(db, dataset_id, new_state, mode=body.mode if new_state else None)
    return {"published": new_state, "mode": body.mode if new_state else None}


@router.get("/datasets/{dataset_id}/public")
async def get_public_dashboard(dataset_id: str, db=Depends(get_db)):
    row = await get_published_dashboard(db, dataset_id)
    if not row or not row["published"] or not row["published_mode"]:
        raise HTTPException(status_code=404, detail="Dashboard not available")

    plan = await get_cached_dashboard_plan(db, dataset_id, mode=row["published_mode"])
    if not plan:
        raise HTTPException(status_code=404, detail="Dashboard not available")

    return {
        "mode": row["published_mode"],
        "charts": plan.get("charts", []),
    }