from fastapi import APIRouter, HTTPException
from app.services.database import get_dataset_state
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

@router.get("/datasets/{dataset_id}/state")
def get_state(dataset_id: str):
    state = get_dataset_state(dataset_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dataset not found")

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
            "cards_created": len(plan.get("charts", [])) if plan else 0,
            "cards": [
                {"card_id": None, "chart_title": c["chart_title"]}
                for c in plan.get("charts", [])
            ] if plan else [],
            "errors": []
        }

    return {
        "upload_result": upload_result,
        "semantics":     state["semantics"],
        "plan":          state["plan"],
        "dashboard_result": dashboard_result,
    }