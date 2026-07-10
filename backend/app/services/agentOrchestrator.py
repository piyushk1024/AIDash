import json
import logging
from typing import AsyncGenerator
from app.services.llm import generate_with_tools
from app.services.agentTools import TOOL_SCHEMAS, SYSTEM_PROMPT
from app.services.agentDispatch import (
    dispatch_inspect_data,
    dispatch_build_and_add_chart,
    dispatch_edit_existing_chart,
    dispatch_delete_existing_chart,
)
from app.schemas.chartTypes import CHART_TYPE_GUIDANCE
from app.services.database import json_default
from app.config import settings

logger = logging.getLogger(__name__)

_EXISTING_ONLY_TOOLS = {"edit_existing_chart", "delete_existing_chart"}


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


def _build_existing_charts_section(existing_charts: list | None) -> str:
    if not existing_charts:
        return ""

    lines = ["\nExisting dashboard (already built — do not duplicate these):"]
    for c in existing_charts:
        lines.append(
            f'  - card_id="{c.get("card_id")}" | "{c.get("chart_title")}" | '
            f'{c.get("chart_type")} | sql: {c.get("sql")}'
        )
    lines.append("")
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


def _get_available_tools(inspect_count: int, has_existing_charts: bool) -> list[dict]:
    tools = TOOL_SCHEMAS
    if inspect_count >= settings.AGENT_MAX_INSPECT_CALLS:
        tools = [t for t in tools if t["function"]["name"] != "inspect_data"]
    if not has_existing_charts:
        tools = [t for t in tools if t["function"]["name"] not in _EXISTING_ONLY_TOOLS]
    return tools


async def stream_agent(
    goal: str,
    table_name: str,
    field_map: dict,
    semantics: dict,
    profile: dict,
    pool,
    existing_charts: list | None = None,
) -> AsyncGenerator[dict, None]:
    field_reference = _build_field_reference(field_map, semantics)
    profile_summary = _build_profile_summary(profile)
    existing_charts_section = _build_existing_charts_section(existing_charts)
    has_existing_charts = bool(existing_charts)

    system_content = SYSTEM_PROMPT.format(
        table_name=table_name,
        field_reference=field_reference,
        profile_summary=profile_summary,
        existing_charts_section=existing_charts_section,
        goal=goal,
        chart_type_guidance=CHART_TYPE_GUIDANCE,
    )

    messages = [{"role": "user", "content": system_content}]
    charts_built = list(existing_charts) if existing_charts else []
    inspect_count = 0

    async def execute_sql_fn(sql: str) -> dict:
        from app.services.queryExecutor import execute_raw_query
        return await execute_raw_query(pool, sql)

    for iteration in range(settings.AGENT_MAX_ITERATIONS):
        available_tools = _get_available_tools(inspect_count, has_existing_charts)
        msg = await generate_with_tools(messages, available_tools, stage="agent")
        messages.append(_build_assistant_message(msg))

        if not msg.tool_calls:
            logger.warning("Agent returned text at iteration %d — treating as finish", iteration)
            break

        tool_call = msg.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        reasoning = tool_args.get("reasoning", "") or tool_args.get("summary", "")

        yield {
            "type": "step_started",
            "step": iteration + 1,
            "tool": tool_name,
            "reasoning": reasoning,
        }

        if tool_name == "finish":
            summary = tool_args.get("summary", "Done.")
            observation = {"acknowledged": True}
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(observation, default=json_default),
            })
            yield {
                "type": "finish",
                "step": iteration + 1,
                "tool": "finish",
                "reasoning": summary,
                "observation": observation,
                "charts_built": charts_built,
            }
            break

        if tool_name == "inspect_data":
            observation, trace_entry = await dispatch_inspect_data(
                tool_args=tool_args, execute_sql_fn=execute_sql_fn, step=iteration + 1,
            )
            inspect_count += 1
            yield {"type": "inspect_result", **trace_entry}

        elif tool_name == "build_and_add_chart":
            observation, trace_entry, healed = await dispatch_build_and_add_chart(
                tool_args=tool_args, pool=pool, field_map=field_map,
                charts_built=charts_built, step=iteration + 1,
            )
            if healed:
                yield {"type": "healing", "step": iteration + 1, "chart_title": tool_args.get("chart_title", "")}
            yield {"type": "chart_built" if observation.get("success") else "chart_failed", **trace_entry}

        elif tool_name == "edit_existing_chart":
            observation, trace_entry, healed = await dispatch_edit_existing_chart(
                tool_args=tool_args, pool=pool, field_map=field_map,
                charts_built=charts_built, step=iteration + 1,
            )
            if healed:
                yield {"type": "healing", "step": iteration + 1, "chart_title": tool_args.get("chart_title", "")}
            yield {"type": "chart_edited" if observation.get("success") else "chart_edit_failed", **trace_entry}

        elif tool_name == "delete_existing_chart":
            observation, trace_entry = await dispatch_delete_existing_chart(
                tool_args=tool_args, charts_built=charts_built, step=iteration + 1,
            )
            yield {"type": "chart_deleted" if observation.get("success") else "chart_delete_failed", **trace_entry}

        else:
            observation = {"error": f"Unknown tool: {tool_name}"}
            trace_entry = {
                "step": iteration + 1, "tool": tool_name, "reasoning": "", "observation": observation,
            }
            yield {"type": "phase_error", **trace_entry}

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(observation, default=json_default),
        })


async def run_agent(
    goal: str,
    table_name: str,
    field_map: dict,
    semantics: dict,
    profile: dict,
    pool,
    existing_charts: list | None = None,
) -> dict:
    """
    Wrapper around stream_agent for the existing synchronous route.
    Collects all events and returns the same shape as before.
    """
    charts_built = []
    trace = []

    async for event in stream_agent(
        goal=goal,
        table_name=table_name,
        field_map=field_map,
        semantics=semantics,
        profile=profile,
        pool=pool,
        existing_charts=existing_charts,
    ):
        event_type = event["type"]

        if event_type == "finish":
            charts_built = event.get("charts_built", [])

        if event_type not in ("step_started", "healing"):
            trace_entry = {k: v for k, v in event.items() if k not in ("type", "charts_built")}
            trace.append(trace_entry)

    return {
        "charts_built": charts_built,
        "trace": trace,
    }