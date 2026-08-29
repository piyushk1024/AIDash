import logging
import uuid
from app.services.queryExecutor import execute_chart_query
from app.services.selfHealer import heal_chart_spec

logger = logging.getLogger(__name__)


async def build_card_with_healing(
    chart: dict,
    field_map: dict,
    pool,
    table_name: str,
    existing_id: str | None = None,
    profile: dict | None = None,
) -> tuple[dict | None, dict | None]:
    """
    Runs chart's SQL via queryExecutor and builds a stored Plotly card result.
    Single entry point for pipeline create, pipeline update, NL add, and NL
    edit alike — all four are "run this spec, store the result" with no
    distinction at this layer (replaces the old separate create_card_with_healing
    / update_card_with_healing pair, and the old two-stage Metabase healing —
    queryExecutor validates + executes + builds the spec in one call, so
    there's no separate post-creation render-validation stage to heal against).

    existing_id is passed on update/edit to preserve the card's stable id
    across a rebuild; omitted (None) generates a fresh one. Caller decides
    whether the result gets appended or replaces an existing entry by id —
    this function doesn't know or care which.

    Returns (result, None) on success, (None, error_entry) on failure.
    """
    original_chart = chart.copy()
    card_id = existing_id or uuid.uuid4().hex[:8]
    healed = False

    try:
        query_result = await execute_chart_query(pool, chart, table_name, profile=profile)
    except Exception as e:
        logger.warning(f"Chart query failed for '{chart.get('chart_title')}': {e}")
        if not chart.get("sql"):
            logger.error("Chart '%s' failed permanently, no SQL to heal. error=%s",
                         original_chart.get("chart_title"), str(e))
            return None, _error_entry(original_chart)
        try:
            chart = await heal_chart_spec(chart, str(e), field_map, table_name)
            query_result = await execute_chart_query(pool, chart, table_name, profile=profile)
            healed = True
        except Exception as e2:
            logger.error("Chart '%s' failed permanently. error=%s, heal_error=%s",
                         original_chart.get("chart_title"), str(e), str(e2))
            return None, _error_entry(original_chart)

    if healed:
        return _healed_entry(original_chart, chart, card_id, query_result), None
    return _clean_entry(chart, card_id, query_result), None


def _clean_entry(chart: dict, card_id: str, query_result: dict) -> dict:
    return {
        "card_id":     card_id,
        "chart_title": chart.get("chart_title", "Untitled chart"),
        "chart_type":  chart.get("chart_type"),
        "sql":         chart.get("sql"),
        "columns":     chart.get("columns"),
        "rows":        query_result["rows"],
        "spec":        query_result["spec"],
        "healed":      False,
    }


def _healed_entry(original: dict, healed: dict, card_id: str, query_result: dict) -> dict:
    return {
        "card_id":     card_id,
        "chart_title": healed["chart_title"],
        "chart_type":  healed.get("chart_type"),
        "sql":         healed.get("sql"),
        "rows":        query_result["rows"],
        "spec":        query_result["spec"],
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