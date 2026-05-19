import logging
from app.services.metabaseClient import create_card, validate_card_query, delete_card
from app.services.selfHealer import heal_chart_spec

logger = logging.getLogger(__name__)


def create_card_with_healing(
    token: str,
    chart: dict,
    table_id: int,
    field_map: dict,
    database_id: int,
) -> tuple[dict | None, dict | None]:
    original_chart = chart.copy()
    healed = False

    # Stage 1 — create_card failure
    try:
        card = create_card(token, chart, table_id, field_map, database_id)
    except Exception as e:
        logger.warning(f"create_card failed for '{chart.get('chart_title')}': {e}")
        try:
            chart = heal_chart_spec(chart, str(e), field_map)
            card = create_card(token, chart, table_id, field_map, database_id)
            healed = True
        except Exception as e2:
            return None, _error_entry(original_chart, str(e), str(e2))

    # Stage 2 — Metabase render failure
    query_error = validate_card_query(token, card["id"])
    if query_error:
        logger.warning(f"Card validation failed for '{chart.get('chart_title')}': {query_error}")
        pre_heal_chart = chart.copy()
        try:
            chart = heal_chart_spec(chart, query_error, field_map)
            delete_card(token, card["id"])
            card = create_card(token, chart, table_id, field_map, database_id)
            retry_error = validate_card_query(token, card["id"])
            if retry_error:
                delete_card(token, card["id"])
                return None, _error_entry(pre_heal_chart, query_error, retry_error)
            healed = True
        except Exception as e3:
            return None, _error_entry(pre_heal_chart, query_error, str(e3))

    if healed:
        return _healed_entry(original_chart, chart, card["id"]), None
    return _clean_entry(chart, card["id"]), None


def _clean_entry(chart: dict, card_id: int) -> dict:
    return {
        "card_id": card_id,
        "chart_title": chart["chart_title"],
        "chart_type": chart["chart_type"],
        "healed": False,
    }


def _healed_entry(original: dict, healed: dict, card_id: int) -> dict:
    return {
        "card_id": card_id,
        "chart_title": healed["chart_title"],
        "chart_type": healed.get("chart_type"),
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
        },
    }


def _error_entry(chart: dict, error: str, heal_error: str) -> dict:
    return {
        "chart_title": chart.get("chart_title"),
        "chart_type": chart.get("chart_type"),
        "aggregation": chart.get("aggregation"),
        "x_axis": chart.get("x_axis"),
        "y_axis": chart.get("y_axis"),
        "error": error,
        "heal_error": heal_error,
    }