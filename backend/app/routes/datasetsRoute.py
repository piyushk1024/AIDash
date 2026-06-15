from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import get_current_user,get_db
from app.services.database import (
    get_dataset_state,
    get_dataset_owner,
    get_dataset_metadata,
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
        "metabase_table_id": metadata["metabase_table_id"],
        "field_map": metadata["field_map"],
    }

    # Reconstruct dashboardResult if a dashboard was created
    dashboard_result = None
    if metadata.get("metabase_dashboard_id"):
        dashboard_id = metadata["metabase_dashboard_id"]
        plan = state["plan"]
        dashboard_result = {
            "dashboard_id": dashboard_id,
            "dashboard_url": f"{settings.METABASE_URL}/dashboard/{dashboard_id}",
            "public_url": metadata.get("public_url"),
            "published": metadata.get("published", False),
            "cards_created": len(plan.get("charts", [])) if plan else 0,
            "cards": [
                {
                    "card_id": c.get("card_id"),
                    "chart_title": c["chart_title"],
                    "chart_type": c.get("chart_type"),
                    "healed": c.get("healed", False),
                    "original_chart": c.get("original_chart"),
                    "healed_chart": c.get("healed_chart"),
                }
                for c in plan.get("charts", [])
            ] if plan else [],
            "errors": plan.get("errors", []) if plan else []
        }

    return {
        "upload_result": upload_result,
        "semantics":     state["semantics"],
        "plan":          state["plan"],
        "dashboard_result": dashboard_result,
    }

@router.post("/datasets/{dataset_id}/publish")
async def publish_dashboard(
    dataset_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner = await get_dataset_owner(db, dataset_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata.get("metabase_dashboard_id"):
        raise HTTPException(status_code=400, detail="Build the dashboard before publishing")

    new_state = not metadata.get("published", False)
    await set_published(db, dataset_id, new_state)
    return {"published": new_state}


@router.get("/datasets/{dataset_id}/public")
async def get_public_dashboard(dataset_id: str, db=Depends(get_db)):
    row = await get_published_dashboard(db, dataset_id)
    if not row or not row["published"] or not row["public_url"]:
        raise HTTPException(status_code=404, detail="Dashboard not available")
    return {
        "public_url": row["public_url"],
    }