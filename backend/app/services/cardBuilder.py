import logging
from app.services.metabaseClient import create_card, validate_card_query, delete_card, update_card
from app.services.selfHealer import heal_chart_spec
import httpx

logger = logging.getLogger(__name__)


async def create_card_with_healing(
    token: str,
    http_client: httpx.AsyncClient,
    chart: dict,
    field_map: dict,
    database_id: int,
) -> tuple[dict | None, dict | None]:
    original_chart = chart.copy()
    healed = False

    # Stage 1 — create_card failure
    try:
        card = await create_card(
            token, http_client, chart["chart_title"], chart["chart_type"],
            chart["sql"], database_id,
            x_alias=chart.get("x_alias"), y_alias=chart.get("y_alias"),
            series_alias=chart.get("series_alias"), viz_params=chart.get("viz_params"),
        )
    except Exception as e:
        logger.warning(f"create_card failed for '{chart.get('chart_title')}': {e}")
        try:
            chart = await heal_chart_spec(chart, str(e), field_map)
            card = await create_card(
                token, http_client, chart["chart_title"], chart["chart_type"],
                chart["sql"], database_id,
                x_alias=chart.get("x_alias"), y_alias=chart.get("y_alias"),
                series_alias=chart.get("series_alias"), viz_params=chart.get("viz_params"),
            )
            healed = True
        except Exception as e2:
            logger.error("Chart '%s' failed permanently. stage1_error=%s, heal_error=%s",
                        original_chart.get("chart_title"), str(e), str(e2),)
            return None, _error_entry(original_chart)

    # Stage 2 — Metabase render failure
    query_error = await validate_card_query(token, http_client, card["id"])
    if query_error:
        logger.warning(f"Card validation failed for '{chart.get('chart_title')}': {query_error}")
        pre_heal_chart = chart.copy()
        try:
            chart = await heal_chart_spec(chart, query_error, field_map)
            await delete_card(token, http_client, card["id"])
            card = await create_card(
                token, http_client, chart["chart_title"], chart["chart_type"],
                chart["sql"], database_id,
                x_alias=chart.get("x_alias"), y_alias=chart.get("y_alias"),
                series_alias=chart.get("series_alias"), viz_params=chart.get("viz_params"),
            )
            retry_error = await validate_card_query(token, http_client, card["id"])
            if retry_error:
                await delete_card(token, http_client, card["id"])
                logger.error("Chart '%s' failed permanently. query_error=%s, retry_error=%s",
                    pre_heal_chart.get("chart_title"), query_error, retry_error,)
                return None, _error_entry(pre_heal_chart)
            healed = True
        except Exception as e3:
            logger.error("Chart '%s' heal raised exception. query_error=%s, exception=%s",
                         pre_heal_chart.get("chart_title"), query_error, str(e3),)
            return None, _error_entry(pre_heal_chart)

    if healed:
        return _healed_entry(original_chart, chart, card["id"]), None
    return _clean_entry(chart, card["id"]), None


def _clean_entry(chart: dict, card_id: int) -> dict:
    return {
        "card_id":     card_id,
        "chart_title": chart["chart_title"],
        "chart_type":  chart["chart_type"],
        "sql":         chart["sql"],
        "healed":      False,
    }


def _healed_entry(original: dict, healed: dict, card_id: int) -> dict:
    return {
        "card_id":     card_id,
        "chart_title": healed["chart_title"],
        "chart_type":  healed.get("chart_type"),
        "sql":         healed.get("sql"),
        "healed":      True,
        "original_chart": {
            "chart_title": original.get("chart_title"),
            "chart_type":  original.get("chart_type"),
            "sql":         original.get("sql"),
        },
        "healed_chart": {
            "chart_type": healed.get("chart_type"),
            "sql":        healed.get("sql"),
            "reasoning":  healed.get("reasoning"),
        },
    }

def _error_entry(chart: dict) -> dict:
    return {
        "chart_title": chart.get("chart_title"),
        "chart_type":  chart.get("chart_type"),
        "failed":      True,
    }

async def update_card_with_healing(
    token: str,
    http_client: httpx.AsyncClient,
    chart: dict,
    card_id: int,
    field_map: dict,
    database_id: int,
) -> tuple[dict | None, dict | None]:
    original_chart = chart.copy()
    healed = False

    try:
        card = await update_card(
            token, http_client, card_id, chart["chart_title"], chart["chart_type"],
            chart["sql"], database_id,
            x_alias=chart.get("x_alias"), y_alias=chart.get("y_alias"),
            series_alias=chart.get("series_alias"), viz_params=chart.get("viz_params"),
        )
    except Exception as e:
        logger.warning(f"update_card failed for '{chart.get('chart_title')}': {e}")
        try:
            chart = await heal_chart_spec(chart, str(e), field_map)
            card = await update_card(
                token, http_client, card_id, chart["chart_title"], chart["chart_type"],
                chart["sql"], database_id,
                x_alias=chart.get("x_alias"), y_alias=chart.get("y_alias"),
                series_alias=chart.get("series_alias"), viz_params=chart.get("viz_params"),
            )
            healed = True
        except Exception as e2:
            logger.error("Chart update '%s' failed permanently. stage1_error=%s, heal_error=%s",
                        original_chart.get("chart_title"), str(e), str(e2))
            return None, _error_entry(original_chart)

    query_error = await validate_card_query(token, http_client, card_id)
    if query_error:
        pre_heal_chart = chart.copy()
        try:
            chart = await heal_chart_spec(chart, query_error, field_map)
            card = await update_card(
                token, http_client, card_id, chart["chart_title"], chart["chart_type"],
                chart["sql"], database_id,
                x_alias=chart.get("x_alias"), y_alias=chart.get("y_alias"),
                series_alias=chart.get("series_alias"), viz_params=chart.get("viz_params"),
            )
            retry_error = await validate_card_query(token, http_client, card_id)
            if retry_error:
                logger.error("Chart update '%s' failed permanently. query_error=%s, retry_error=%s",
                    pre_heal_chart.get("chart_title"), query_error, retry_error)
                return None, _error_entry(pre_heal_chart)
            healed = True
        except Exception as e3:
            logger.error("Chart update '%s' heal raised exception. query_error=%s, exception=%s",
                         pre_heal_chart.get("chart_title"), query_error, str(e3))
            return None, _error_entry(pre_heal_chart)

    if healed:
        return _healed_entry(original_chart, chart, card_id), None
    return _clean_entry(chart, card_id), None