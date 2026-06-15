from fastapi import APIRouter, Depends, HTTPException
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
    get_dataset_owner
)
from app.dependencies import get_db, get_http_client, get_app_state, require_editor
from app.config import settings

router = APIRouter()


@router.post("/create-metabase-dashboard/{dataset_id}")
async def create_metabase_dashboard(
    dataset_id: str,
    db=Depends(get_db),
    http_client=Depends(get_http_client),
    app_state=Depends(get_app_state),
    current_user=Depends(require_editor),
):
    plan = await get_cached_dashboard_plan(db, dataset_id)
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="No dashboard plan found. Run /generate-dashboard-plan first.",
        )
    
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No dataset metadata found. Re-upload the CSV to generate field mappings.",
        )

    field_map = metadata["field_map"]

    token = await get_session_token(http_client, app_state)
    database_id = await get_database_id(token, http_client)

    existing_dashboard_id = metadata.get("metabase_dashboard_id")
    if existing_dashboard_id:
        try:
            card_ids = await get_dashboard_card_ids(token, http_client, existing_dashboard_id)
            await delete_dashboard(token, http_client, existing_dashboard_id)
            for card_id in card_ids:
                await delete_card(token, http_client, card_id)
        except Exception:
            pass

    dashboard_id = await create_dashboard(token, http_client, plan["dashboard_title"])
    public_url = await create_public_link(token, http_client, dashboard_id)
    await persist_metabase_dashboard_id(db, dataset_id, dashboard_id, public_url)

    created_cards = []
    errors = []
    updated_charts = []

    for i, chart in enumerate(plan["charts"]):
        result, error = await create_card_with_healing(token, http_client, chart, field_map, database_id)
        if error:
            errors.append(error)
            updated_charts.append(chart)
            continue
        await add_card_to_dashboard(token, http_client, dashboard_id, result["card_id"], i)
        created_cards.append(result)
        updated_chart = chart.copy()
        updated_chart["card_id"] = result["card_id"]
        if result.get("healed"):
            updated_chart["healed"] = True
            updated_chart["original_chart"] = result.get("original_chart")
            updated_chart["healed_chart"] = result.get("healed_chart")
        updated_charts.append(updated_chart)

    updated_plan = {**plan, "charts": updated_charts, "errors": errors}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return {
        "dashboard_id": dashboard_id,
        "dashboard_url": f"{settings.METABASE_URL}/dashboard/{dashboard_id}",
        "public_url": public_url,
        "published": False,  
        "cards_created": len(created_cards),
        "cards": created_cards,
        "errors": errors,
    }