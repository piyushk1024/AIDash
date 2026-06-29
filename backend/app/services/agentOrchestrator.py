import json
import logging
from app.services.llm import generate_with_tools
from app.services.sqlGuard import validate_sql
from app.services.cardBuilder import create_card_with_healing
from app.services.metabaseClient import execute_sql_query, add_card_to_dashboard
from app.services.agentTools import TOOL_SCHEMAS, SYSTEM_PROMPT
from app.config import settings

logger = logging.getLogger(__name__)


def _build_field_reference(field_map: dict, semantics: dict) -> str:
    role_map = {}
    for category in ("date_columns", "dimensions", "measures", "flags", "identifiers", "unknown"):
        for col in semantics.get(category, []):
            role_map[col["column"]] = col["semantic_role"]

    lines = []
    for col, meta in field_map.items():
        role = role_map.get(col, "unknown")
        lines.append(f'  - "{col}" | {meta["base_type"]} | {role}')

    return "\n".join(lines)


def _build_profile_summary(profile: dict) -> str:
    lines = []
    for col in profile.get("columns", []):
        name = col["column_name"]
        stats = col.get("stats", {})
        if stats:
            lines.append(f"  - {name}: {stats}")
    return "\n".join(lines)


def _build_assistant_message(msg) -> dict:
    """
    Serialises a LiteLLM message object into a plain dict for the conversation history.
    Strips provider-specific fields (e.g. Gemini thought_signature) that would
    cause serialisation errors on subsequent LiteLLM calls.
    """
    if msg.tool_calls:
        serialised_tool_calls = []
        for tc in msg.tool_calls:
            serialised_tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })
        return {"role": "assistant", "content": None, "tool_calls": serialised_tool_calls}

    return {"role": "assistant", "content": msg.content}


def _get_available_tools(inspect_count: int) -> list[dict]:
    """
    Returns the tool subset available at the current point in the loop.
    Once the inspection budget is exhausted, inspect_data is removed —
    the agent can only build or finish.
    finish is always available.
    """
    if inspect_count >= settings.AGENT_MAX_INSPECT_CALLS:
        return [t for t in TOOL_SCHEMAS if t["function"]["name"] != "inspect_data"]
    return TOOL_SCHEMAS


async def _dispatch_inspect_data(tool_args: dict, execute_sql_fn, step: int) -> tuple[dict, dict]:
    sql = tool_args["sql"]
    reasoning = tool_args.get("reasoning", "")

    try:
        validate_sql(sql, context="agent_inspect")
    except ValueError as e:
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


async def _dispatch_build_and_add_chart(
    tool_args: dict,
    token: str,
    http_client,
    database_id: int,
    dashboard_id: int,
    field_map: dict,
    charts_built: list,
    step: int,
) -> tuple[dict, dict]:
    chart_spec = {
        "chart_title": tool_args["chart_title"],
        "chart_type": tool_args["chart_type"],
        "sql": tool_args["sql"],
        "x_alias": tool_args.get("x_alias"),
        "y_alias": tool_args.get("y_alias"),
    }
    reasoning = tool_args.get("reasoning", "")

    try:
        validate_sql(chart_spec["sql"], context=chart_spec["chart_title"])
    except ValueError as e:
        observation = {"error": "SQL validation failed."}
        trace_entry = {
            "step": step,
            "tool": "build_and_add_chart",
            "reasoning": reasoning,
            "chart_title": chart_spec["chart_title"],
            "observation": observation,
        }
        return observation, trace_entry

    result, error = await create_card_with_healing(token, http_client, chart_spec, field_map, database_id)

    if error:
        logger.error("Agent chart creation failed for '%s': %s", chart_spec["chart_title"], error)
        observation = {"error": "Chart creation failed after healing attempt."}
    else:
        position = len(charts_built)
        await add_card_to_dashboard(token, http_client, dashboard_id, result["card_id"], position)
        charts_built.append({**chart_spec, "card_id": result["card_id"]})
        observation = {
            "success": True,
            "card_id": result["card_id"],
            "chart_title": chart_spec["chart_title"],
        }

    trace_entry = {
        "step": step,
        "tool": "build_and_add_chart",
        "reasoning": reasoning,
        "chart_title": chart_spec["chart_title"],
        "chart_type": chart_spec["chart_type"],
        "observation": observation,
    }
    return observation, trace_entry


async def run_agent(
    goal: str,
    table_name: str,
    field_map: dict,
    semantics: dict,
    profile: dict,
    dashboard_id: int,
    token: str,
    http_client,
    database_id: int,
) -> dict:
    field_reference = _build_field_reference(field_map, semantics)
    profile_summary = _build_profile_summary(profile)

    system_content = SYSTEM_PROMPT.format(
        table_name=table_name,
        field_reference=field_reference,
        profile_summary=profile_summary,
        goal=goal,
    )

    messages = [{"role": "user", "content": system_content}]
    trace = []
    charts_built = []
    inspect_count = 0

    async def execute_sql_fn(sql: str) -> dict:
        return await execute_sql_query(token, http_client, sql, database_id)

    for iteration in range(settings.AGENT_MAX_ITERATIONS):
        available_tools = _get_available_tools(inspect_count)
        msg = await generate_with_tools(messages, available_tools, stage="agent")

        messages.append(_build_assistant_message(msg))

        if not msg.tool_calls:
            logger.warning("Agent returned text at iteration %d — treating as finish", iteration)
            break

        tool_call = msg.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        if tool_name == "finish":
            summary = tool_args.get("summary", "Dashboard complete.")
            trace.append({
                "step": iteration + 1,
                "tool": "finish",
                "reasoning": summary,
                "observation": {"acknowledged": True},
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps({"acknowledged": True}),
            })
            break

        if tool_name == "inspect_data":
            observation, trace_entry = await _dispatch_inspect_data(
                tool_args=tool_args,
                execute_sql_fn=execute_sql_fn,
                step=iteration + 1,
            )
            inspect_count += 1

        elif tool_name == "build_and_add_chart":
            observation, trace_entry = await _dispatch_build_and_add_chart(
                tool_args=tool_args,
                token=token,
                http_client=http_client,
                database_id=database_id,
                dashboard_id=dashboard_id,
                field_map=field_map,
                charts_built=charts_built,
                step=iteration + 1,
            )

        else:
            observation = {"error": f"Unknown tool: {tool_name}"}
            trace_entry = {
                "step": iteration + 1,
                "tool": tool_name,
                "reasoning": "",
                "observation": observation,
            }

        trace.append(trace_entry)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(observation),
        })

    return {
        "charts_built": charts_built,
        "trace": trace,
        "dashboard_id": dashboard_id,
    }