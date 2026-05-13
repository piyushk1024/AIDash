from fastapi import APIRouter, HTTPException
from app.services.metabaseClient import (
    get_session_token,
    create_card,
    create_dashboard,
    add_card_to_dashboard,
    delete_dashboard,
    delete_card,
    get_dashboard_card_ids,
    create_public_link,
    get_database_id,
    validate_card_query
)

from app.services.database import get_cached_dashboard_plan, get_dataset_metadata, persist_metabase_dashboard_id
from app.services.selfHealer import heal_chart_spec
import logging



from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

def _chart_error(chart: dict, error: str, heal_error: str) -> dict:
    return {
        "chart_title": chart.get("chart_title"),
        "chart_type": chart.get("chart_type"),
        "aggregation": chart.get("aggregation"),
        "x_axis": chart.get("x_axis"),
        "y_axis": chart.get("y_axis"),
        "error": error,
        "heal_error": heal_error
    }

def _chart_healed(original: dict, healed: dict) -> dict:
    return {
        "chart_title": healed["chart_title"],
        "card_id": None,  # filled in by caller
        "healed": True,
        "original_chart": {
            "chart_title": original.get("chart_title"),
            "chart_type": original.get("chart_type"),
            "aggregation": original.get("aggregation"),
            "x_axis": original.get("x_axis"),
            "y_axis": original.get("y_axis"),
        },
        "healed_chart": {
            "chart_type": healed.get("chart_type"),
            "aggregation": healed.get("aggregation"),
            "x_axis": healed.get("x_axis"),
            "y_axis": healed.get("y_axis"),
            "reasoning": healed.get("reasoning"),
        }
    }

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
    # print(f"=== existing_dashboard_id: {existing_dashboard_id} ===")
    if existing_dashboard_id:
        try:
            card_ids = get_dashboard_card_ids(token, existing_dashboard_id)
            delete_dashboard(token, existing_dashboard_id)
            for card_id in card_ids:
                delete_card(token, card_id)
        except Exception:
            pass  # If already gone in Metabase, continue anyway
    dashboard_id = create_dashboard(token, plan["dashboard_title"])
    public_url = create_public_link(token, dashboard_id)
    persist_metabase_dashboard_id(dataset_id, dashboard_id, public_url)  
    # dashboard_id = create_dashboard(token, plan["dashboard_title"])
    
    

    created_cards = []
    errors = []
   

    for i, chart in enumerate(plan["charts"]):
        healed = False
        original_chart = chart.copy()

        try:
            card = create_card(token, chart, table_id, field_map, database_id)
        except Exception as e:
            logger.warning(f"create_card failed for '{chart.get('chart_title')}': {e}")
            try:
                healed_chart = heal_chart_spec(chart, str(e), field_map)
                card = create_card(token, healed_chart, table_id, field_map, database_id)
                chart = healed_chart
                healed = True
            except Exception as e2:
                errors.append(_chart_error(original_chart, str(e), str(e2)))
                continue

        query_error = validate_card_query(token, card["id"])
        if query_error:
            logger.warning(f"Card validation failed for '{chart.get('chart_title')}': {query_error}")
            original_chart = chart.copy()
            try:
                healed_chart = heal_chart_spec(chart, query_error, field_map)
                delete_card(token, card["id"])
                card = create_card(token, healed_chart, table_id, field_map, database_id)
                retry_error = validate_card_query(token, card["id"])
                if retry_error:
                    delete_card(token, card["id"])
                    errors.append(_chart_error(original_chart, query_error, retry_error))
                    continue
                chart = healed_chart
                healed = True
            except Exception as e3:
                errors.append(_chart_error(original_chart, query_error, str(e3)))
                continue

        add_card_to_dashboard(token, dashboard_id, card["id"], i)

        if healed:
            entry = _chart_healed(original_chart, chart)
            entry["card_id"] = card["id"]
            created_cards.append(entry)
        else:
            created_cards.append({
                "chart_title": chart["chart_title"],
                "card_id": card["id"],
                "healed": False
            })
    return {
        "dashboard_id": dashboard_id,
        "dashboard_url": f"{settings.METABASE_URL}/dashboard/{dashboard_id}",   
        "public_url": public_url,
        "cards_created": len(created_cards),
        "cards": created_cards,
        "errors": errors
    }