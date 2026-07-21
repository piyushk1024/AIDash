import logging
from app.services.sqlGuard import validate_sql
from app.services.cardBuilder import build_card_with_healing

logger = logging.getLogger(__name__)


def _extract_chart_spec(tool_args: dict) -> dict:
    return {
        "chart_title": tool_args["chart_title"],
        "chart_type": tool_args["chart_type"],
        "sql": tool_args["sql"],
        "x_alias": tool_args.get("x_alias"),
        "y_alias": tool_args.get("y_alias"),
        "series_alias": tool_args.get("series_alias"),
        "viz_params": tool_args.get("viz_params"),
    }


async def dispatch_inspect_data(tool_args: dict, execute_sql_fn, step: int) -> tuple[dict, dict]:
    sql = tool_args["sql"]
    reasoning = tool_args.get("reasoning", "")

    try:
        validate_sql(sql, context="agent_inspect")
    except ValueError:
        observation = {"error": "SQL validation failed."}
        trace_entry = {
            "step": step,
            "tool": "inspect_data",
            "reasoning": reasoning,
            "sql": sql,
            "observation": observation,
        }
        return observation, trace_entry

    try:
        result = await execute_sql_fn(sql)
        result["rows"] = result["rows"][:20]
        observation = result
    except Exception as e:
        logger.error("Agent inspect_data execution failed: %s", e)
        observation = {"error": "Query execution failed."}

    trace_entry = {
        "step": step,
        "tool": "inspect_data",
        "reasoning": reasoning,
        "sql": sql,
        "observation": observation,
    }
    return observation, trace_entry


async def dispatch_build_and_add_chart(
    tool_args: dict,
    pool,
    field_map: dict,
    charts_built: list,
    step: int,
) -> tuple[dict, dict, bool]:
    reasoning = tool_args.get("reasoning", "")

    required = ("chart_title", "chart_type", "sql")
    missing = [f for f in required if not tool_args.get(f)]
    if missing:
        observation = {"error": f"Missing required field(s): {missing}"}
        trace_entry = {
            "step": step,
            "tool": "build_and_add_chart",
            "reasoning": reasoning,
            "chart_title": tool_args.get("chart_title", "unknown"),
            "observation": observation,
        }
        return observation, trace_entry, False

    chart_spec = _extract_chart_spec(tool_args)

    try:
        validate_sql(chart_spec["sql"], context=chart_spec["chart_title"])
    except ValueError:
        observation = {"error": "SQL validation failed."}
        trace_entry = {
            "step": step,
            "tool": "build_and_add_chart",
            "reasoning": reasoning,
            "chart_title": chart_spec["chart_title"],
            "observation": observation,
        }
        return observation, trace_entry, False

    result, error = await build_card_with_healing(chart_spec, field_map, pool)
    healed = bool(result and result.get("healed"))

    if error:
        logger.error("Agent chart creation failed for '%s': %s", chart_spec["chart_title"], error)
        observation = {"error": "Chart creation failed after healing attempt."}
    else:
        charts_built.append(result)
        observation = {
            "success": True,
            "card_id": result["card_id"],
            "chart_title": chart_spec["chart_title"],
        }

    trace_entry = {
        "step": step,
        "tool": "build_and_add_chart",
        "reasoning": reasoning,
        "card_id": result.get("card_id") if result else None,
        "chart_title": chart_spec["chart_title"],
        "chart_type": chart_spec["chart_type"],
        "sql": chart_spec["sql"],
        "x_alias": chart_spec["x_alias"],
        "y_alias": chart_spec["y_alias"],
        "series_alias": chart_spec["series_alias"],
        "viz_params": chart_spec["viz_params"],
        "healed": healed,
        "rows": result.get("rows") if result else None,
        "spec": result.get("spec") if result else None,
        "observation": observation,
    }
    return observation, trace_entry, healed


async def dispatch_edit_existing_chart(
    tool_args: dict,
    pool,
    field_map: dict,
    charts_built: list,
    step: int,
) -> tuple[dict, dict, bool]:
    reasoning = tool_args.get("reasoning", "")
    card_id = tool_args.get("card_id")

    required = ("card_id", "chart_title", "chart_type", "sql")
    missing = [f for f in required if not tool_args.get(f)]
    if missing:
        observation = {"error": f"Missing required field(s): {missing}"}
        trace_entry = {
            "step": step, "tool": "edit_existing_chart", "reasoning": reasoning,
            "card_id": card_id, "observation": observation,
        }
        return observation, trace_entry, False

    match_index = next((i for i, c in enumerate(charts_built) if c.get("card_id") == card_id), None)
    if match_index is None:
        observation = {"error": f"No existing chart with card_id '{card_id}'."}
        trace_entry = {
            "step": step, "tool": "edit_existing_chart", "reasoning": reasoning,
            "card_id": card_id, "observation": observation,
        }
        return observation, trace_entry, False

    chart_spec = _extract_chart_spec(tool_args)

    try:
        validate_sql(chart_spec["sql"], context=chart_spec["chart_title"])
    except ValueError:
        observation = {"error": "SQL validation failed."}
        trace_entry = {
            "step": step, "tool": "edit_existing_chart", "reasoning": reasoning,
            "card_id": card_id, "chart_title": chart_spec["chart_title"], "observation": observation,
        }
        return observation, trace_entry, False

    result, error = await build_card_with_healing(chart_spec, field_map, pool, existing_id=card_id)
    healed = bool(result and result.get("healed"))

    if error:
        logger.error("Agent chart edit failed for card_id '%s': %s", card_id, error)
        observation = {"error": "Chart edit failed after healing attempt."}
    else:
        charts_built[match_index] = result
        observation = {"success": True, "card_id": card_id, "chart_title": chart_spec["chart_title"]}

    trace_entry = {
        "step": step,
        "tool": "edit_existing_chart",
        "reasoning": reasoning,
        "card_id": card_id,
        "chart_title": chart_spec["chart_title"],
        "chart_type": chart_spec["chart_type"],
        "sql": chart_spec["sql"],
        "x_alias": chart_spec["x_alias"],
        "y_alias": chart_spec["y_alias"],
        "series_alias": chart_spec["series_alias"],
        "viz_params": chart_spec["viz_params"],
        "healed": healed,
        "rows": result.get("rows") if result else None,
        "spec": result.get("spec") if result else None,
        "observation": observation,
    }
    return observation, trace_entry, healed


async def dispatch_delete_existing_chart(
    tool_args: dict,
    charts_built: list,
    step: int,
) -> tuple[dict, dict]:
    reasoning = tool_args.get("reasoning", "")
    card_id = tool_args.get("card_id")

    match_index = next((i for i, c in enumerate(charts_built) if c.get("card_id") == card_id), None)
    if match_index is None:
        observation = {"error": f"No existing chart with card_id '{card_id}'."}
    else:
        removed = charts_built.pop(match_index)
        observation = {"success": True, "card_id": card_id, "chart_title": removed.get("chart_title")}

    trace_entry = {
        "step": step,
        "tool": "delete_existing_chart",
        "reasoning": reasoning,
        "card_id": card_id,
        "observation": observation,
    }
    return observation, trace_entry