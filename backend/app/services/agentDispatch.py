import logging
from app.services.sqlGuard import validate_sql
from app.services.cardBuilder import build_card_with_healing
from app.services.chartValidation import missing_required_fields, apply_cardinality_guardrail

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


async def dispatch_inspect_data(tool_args: dict, execute_sql_fn, step: int, table_name: str) -> tuple[dict, dict]:
    sql = tool_args["sql"]
    reasoning = tool_args.get("reasoning", "")

    try:
        validate_sql(sql, table_name, context="agent_inspect")
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


async def _dispatch_chart_upsert(
    tool_args: dict,
    pool,
    field_map: dict,
    charts_built: list,
    step: int,
    table_name: str,
    profile: dict | None,
    *,
    mode: str,  # "build" or "edit"
) -> tuple[dict, dict, bool]:
    reasoning = tool_args.get("reasoning", "")
    tool_label = "build_and_add_chart" if mode == "build" else "edit_existing_chart"
    card_id = tool_args.get("card_id") if mode == "edit" else None

    required = ("chart_title", "chart_type", "sql")
    if mode == "edit":
        required = required + ("card_id",)
    missing = missing_required_fields(tool_args, required)
    if missing:
        observation = {"error": f"Missing required field(s): {missing}"}
        trace_entry = {
            "step": step, "tool": tool_label, "reasoning": reasoning,
            "card_id": card_id, "observation": observation,
        }
        return observation, trace_entry, False

    # edit-only: resolve which existing chart is being targeted, before any
    # SQL/cardinality work, so a bad card_id fails fast
    match_index = None
    if mode == "edit":
        match_index = next((i for i, c in enumerate(charts_built) if c.get("card_id") == card_id), None)
        if match_index is None:
            observation = {"error": f"No existing chart with card_id '{card_id}'."}
            trace_entry = {
                "step": step, "tool": tool_label, "reasoning": reasoning,
                "card_id": card_id, "observation": observation,
            }
            return observation, trace_entry, False

    chart_spec = _extract_chart_spec(tool_args)

    try:
        validate_sql(chart_spec["sql"], table_name, context=chart_spec["chart_title"])
    except ValueError:
        observation = {"error": "SQL validation failed."}
        trace_entry = {
            "step": step, "tool": tool_label, "reasoning": reasoning,
            "card_id": card_id, "chart_title": chart_spec["chart_title"], "observation": observation,
        }
        return observation, trace_entry, False

    violation = apply_cardinality_guardrail(chart_spec, profile)
    if violation:
        observation = {"error": violation}
        trace_entry = {
            "step": step, "tool": tool_label, "reasoning": reasoning,
            "card_id": card_id, "chart_title": chart_spec["chart_title"], "observation": observation,
        }
        return observation, trace_entry, False

    existing_id = card_id if mode == "edit" else None
    result, error = await build_card_with_healing(chart_spec, field_map, pool, table_name, existing_id=existing_id,profile=profile)
    healed = bool(result and result.get("healed"))

    if error:
        logger.error("Agent chart %s failed for '%s': %s", mode, chart_spec["chart_title"], error)
        observation = {"error": f"Chart {mode} failed after healing attempt."}
    else:
        result = {**result, "source": "agent"}
        # divergence point: build appends a new chart, edit replaces in place
        if mode == "build":
            charts_built.append(result)
        else:
            charts_built[match_index] = result
        observation = {
            "success": True,
            "card_id": result["card_id"] if mode == "build" else card_id,
            "chart_title": chart_spec["chart_title"],
        }

    trace_entry = {
        "step": step,
        "tool": tool_label,
        "reasoning": reasoning,
        "card_id": result.get("card_id") if result else card_id,
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


async def dispatch_build_and_add_chart(
    tool_args: dict,
    pool,
    field_map: dict,
    charts_built: list,
    step: int,
    table_name: str,
    profile: dict | None = None,
) -> tuple[dict, dict, bool]:
    return await _dispatch_chart_upsert(
        tool_args, pool, field_map, charts_built, step, table_name, profile, mode="build",
    )


async def dispatch_edit_existing_chart(
    tool_args: dict,
    pool,
    field_map: dict,
    charts_built: list,
    step: int,
    table_name: str,
    profile: dict | None = None,
) -> tuple[dict, dict, bool]:
    return await _dispatch_chart_upsert(
        tool_args, pool, field_map, charts_built, step, table_name, profile, mode="edit",
    )
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