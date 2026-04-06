from fastapi import APIRouter, HTTPException
from app.services.metabaseClient import (
    get_session_token,
    create_card,
    create_dashboard,
    add_card_to_dashboard
)
from app.services.database import get_cached_dashboard_plan, get_dataset_metadata
from app.config import settings

router = APIRouter()

@router.post("/create-metabase-dashboard/{dataset_id}")
async def create_metabase_dashboard(dataset_id: str):

    plan = get_cached_dashboard_plan(dataset_id)
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="No dashboard plan found. Run /generate-dashboard-plan first."
        )

    metadata = get_dataset_metadata(dataset_id)
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No dataset metadata found. Re-upload the CSV to generate field mappings."
        )

    table_id = metadata["metabase_table_id"]
    field_map = metadata["field_map"]

    token = get_session_token()
    dashboard_id = create_dashboard(token, plan["dashboard_title"])

    created_cards = []
    errors = []

    for i, chart in enumerate(plan["charts"]):
        try:
            card = create_card(token, chart, table_id, field_map)
            add_card_to_dashboard(token, dashboard_id, card["id"], i)
            created_cards.append({
                "chart_title": chart["chart_title"],
                "card_id": card["id"]
            })
        except Exception as e:
            errors.append({
                "chart_title": chart.get("chart_title"),
                "error": str(e)
            })

    return {
        "dashboard_id": dashboard_id,
        "dashboard_url": f"{settings.METABASE_URL}/dashboard/{dashboard_id}",
        "cards_created": len(created_cards),
        "cards": created_cards,
        "errors": errors
    }