from fastapi import APIRouter, HTTPException
from app.services.metabaseClient import (
    get_session_token,
    create_public_link,
    get_database_id,
    get_dashboard_card_ids,
    delete_dashboard,
    delete_card,
    add_card_to_dashboard,
    create_dashboard,
)
from app.services.cardBuilder import create_card_with_healing
from app.services.database import (
    get_cached_dashboard_plan,
    get_dataset_metadata,
    persist_metabase_dashboard_id,
    update_dashboard_plan,
)
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
    database_id = get_database_id(token)

    existing_dashboard_id = metadata.get("metabase_dashboard_id")
    if existing_dashboard_id:
        try:
            card_ids = get_dashboard_card_ids(token, existing_dashboard_id)
            delete_dashboard(token, existing_dashboard_id)
            for card_id in card_ids:
                delete_card(token, card_id)
        except Exception:
            pass

    dashboard_id = create_dashboard(token, plan["dashboard_title"])
    public_url = create_public_link(token, dashboard_id)
    persist_metabase_dashboard_id(dataset_id, dashboard_id, public_url)

    created_cards = []
    errors = []
    updated_charts = []

    for i, chart in enumerate(plan["charts"]):
        result, error = create_card_with_healing(token, chart, table_id, field_map, database_id)
        if error:
            errors.append(error)
            updated_charts.append(chart)  # keep original in plan unchanged
            continue
        add_card_to_dashboard(token, dashboard_id, result["card_id"], i)
        created_cards.append(result)
        # Persist card_id back into the plan entry
        updated_chart = chart.copy()
        updated_chart["card_id"] = result["card_id"]
        updated_charts.append(updated_chart)

    # Persist plan with card_ids stamped in
    updated_plan = {**plan, "charts": updated_charts}
    update_dashboard_plan(dataset_id, updated_plan)

    return {
        "dashboard_id": dashboard_id,
        "dashboard_url": f"{settings.METABASE_URL}/dashboard/{dashboard_id}",
        "public_url": public_url,
        "cards_created": len(created_cards),
        "cards": created_cards,
        "errors": errors,
    }