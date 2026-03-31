from fastapi import APIRouter, HTTPException
from app.services.database import (
    get_cached_semantics,
    get_cached_dashboard_plan,
    persist_dashboard_plan
)
from app.services.dashboardPlanner import generate_dashboard_plan

router = APIRouter()

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

    # Generate plan
    plan = generate_dashboard_plan(dataset_id, semantics)

    # Persist and return
    persist_dashboard_plan(dataset_id, plan)
    return plan