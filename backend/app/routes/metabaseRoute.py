from fastapi import APIRouter, Depends, HTTPException
from app.services.metabaseClient import (
    get_session_token,
    create_public_link,
    get_database_id,
    get_dashboard_cards,
    get_dashboard_card_ids,
    delete_dashboard,
    delete_card,
    create_dashboard,
    sync_dashboard_cards,
)
from app.services.cardBuilder import create_card_with_healing, update_card_with_healing
from app.services.database import (
    get_cached_dashboard_plan,
    get_dataset_metadata,
    persist_metabase_dashboard_id,
    update_dashboard_plan,
    get_dataset_owner,
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
    plan = await get_cached_dashboard_plan(db, dataset_id, mode="pipeline")
    if not plan:
        raise HTTPException(status_code=404, detail="No pipeline dashboard plan found. Run /generate-dashboard-plan first.")

    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="No dataset metadata found. Re-upload the CSV to generate field mappings.")

    field_map = metadata["field_map"]
    token = await get_session_token(http_client, app_state)
    database_id = await get_database_id(token, http_client)

    existing_dashboard_id = metadata.get("metabase_dashboard_id")

    if existing_dashboard_id:
        owning_plan = await get_cached_dashboard_plan(db, dataset_id)
        owning_mode = owning_plan.get("mode", "pipeline") if owning_plan else "pipeline"
        if owning_mode != "pipeline":
            try:
                card_ids = await get_dashboard_card_ids(token, http_client, existing_dashboard_id)
                await delete_dashboard(token, http_client, existing_dashboard_id)
                for card_id in card_ids:
                    await delete_card(token, http_client, card_id)
            except Exception:
                pass
            existing_dashboard_id = None

    old_by_title = {}
    if existing_dashboard_id:
        try:
            existing_cards = await get_dashboard_cards(token, http_client, existing_dashboard_id)
            old_by_title = {c["chart_title"]: c["card_id"] for c in existing_cards}
        except Exception:
            existing_dashboard_id = None

    dashboard_id = existing_dashboard_id or await create_dashboard(token, http_client, plan["dashboard_title"])

    created_cards, errors, updated_charts, final_order = [], [], [], []

    for chart in plan["charts"]:
        title = chart["chart_title"]
        old_card_id = old_by_title.pop(title, None)

        if old_card_id is None:
            result, error = await create_card_with_healing(token, http_client, chart, field_map, database_id)
        elif chart.get("card_id") == old_card_id:
            final_order.append(old_card_id)
            updated_charts.append(chart)
            continue
        else:
            result, error = await update_card_with_healing(token, http_client, chart, old_card_id, field_map, database_id)

        if error:
            errors.append(error)
            updated_charts.append(chart)
            continue

        final_order.append(result["card_id"])
        created_cards.append(result)
        updated_chart = chart.copy()
        updated_chart["card_id"] = result["card_id"]
        if result.get("healed"):
            updated_chart["healed"] = True
            updated_chart["original_chart"] = result.get("original_chart")
            updated_chart["healed_chart"] = result.get("healed_chart")
        updated_charts.append(updated_chart)

    for stale_card_id in old_by_title.values():
        try:
            await delete_card(token, http_client, stale_card_id)
        except Exception:
            pass

    await sync_dashboard_cards(token, http_client, dashboard_id, final_order)

    if not existing_dashboard_id:
        public_url = await create_public_link(token, http_client, dashboard_id)
        await persist_metabase_dashboard_id(db, dataset_id, dashboard_id, public_url)
    else:
        public_url = metadata.get("public_url")

    updated_plan = {**plan, "mode": "pipeline", "charts": updated_charts, "errors": errors}
    await update_dashboard_plan(db, dataset_id, updated_plan)

    return {
        "dashboard_id": dashboard_id,
        "dashboard_url": f"{settings.METABASE_URL}/dashboard/{dashboard_id}",
        "public_url": public_url,
        "published": metadata.get("published", False),
        "cards_created": len(created_cards),
        "cards": updated_charts,
        "errors": errors,
    }