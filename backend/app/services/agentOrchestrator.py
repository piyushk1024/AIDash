import json
import logging
from typing import AsyncGenerator
from app.services.llm import generate, generate_with_tools
from app.services.agentTools import build_tool_schemas, SYSTEM_PROMPT
from app.services.agentDispatch import (
    dispatch_inspect_data,
    dispatch_build_and_add_chart,
    dispatch_edit_existing_chart,
    dispatch_delete_existing_chart,
)
from app.schemas.chartTypes import CHART_TYPE_GUIDANCE, MAP_GUIDANCE
from app.services.database import json_default
from app.config import settings
from app.services.quotaGuard import get_current_user_quota

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
        parts = []

        stats = col.get("stats")
        if stats:
            parts.append(f"stats={stats}")

        distinct_count = col.get("distinct_count")
        if distinct_count is not None:
            parts.append(f"distinct_count={distinct_count}")

        # value_counts arrives pre-sorted descending (profiler.py caps at 10);
        # cap further to top 5 here to bound prompt size on wide datasets.
        value_counts = col.get("value_counts")
        if value_counts:
            top_counts = dict(list(value_counts.items())[:5])
            parts.append(f"value_counts(top5)={top_counts}")

        correlations = col.get("correlations")
        if correlations:
            parts.append(f"correlations={correlations}")

        if parts:
            lines.append(f"  - {name}: " + " | ".join(parts))

    grouped_stats = profile.get("grouped_stats")
    if grouped_stats:
        lines.append(
            "\nGrouped stats (categorical col -> numeric col means per group; "
            "_spread_cv = std/mean across group means, below ~0.10 means the "
            "groups barely differ):"
        )
        for cat_col, group_data in grouped_stats.items():
            lines.append(f"  - {cat_col}: {group_data}")

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


def _get_available_tools(inspect_count: int, has_existing_charts: bool, has_country: bool) -> list[dict]:
    tools = build_tool_schemas(has_country)
    if inspect_count >= settings.AGENT_MAX_INSPECT_CALLS:
        tools = [t for t in tools if t["function"]["name"] != "inspect_data"]
    if not has_existing_charts:
        tools = [t for t in tools if t["function"]["name"] not in _EXISTING_ONLY_TOOLS]
    return tools


SYNTHESIS_PROMPT_TEMPLATE = """You just finished building a dashboard for a business user. Produce two things:
1. A short, professional dashboard title (5-8 words) fit for a report cover page.
2. An explanation, in plain language, of why the charts you built serve the
   stated goal. Write for the person who will read this dashboard, not for
   a developer.

DASHBOARD GOAL (may be empty if no goal was set):
{goal}

CHARTS BUILT:
{charts_summary}

For the rationale: write one short paragraph (3-5 sentences). Reference
specific chart titles where it helps. Do not describe the build process,
tools used, or SQL. Focus only on why this set of charts answers the goal.
If no goal was set, explain what business questions this set of charts
collectively answers.

Respond with ONLY a JSON object in this exact shape, no markdown fences,
no preamble, no text outside the JSON:
{{"dashboard_title": "...", "rationale": "..."}}
"""

def _summarize_charts_for_rationale(charts_built: list[dict]) -> str:
    lines = []
    for c in charts_built:
        title = c.get("chart_title", "?")
        chart_type = c.get("chart_type", "?")
        lines.append(f'  - "{title}" ({chart_type})')
    return "\n".join(lines) if lines else "  (no charts were built)"


async def generate_dashboard_synthesis(goal: str, charts_built: list[dict], trace: list[dict]) -> dict:
    """
    Guaranteed post-loop synthesis step, not agent-callable. Runs once after
    every agent-mode build/nudge completes. Returns {"dashboard_title": str,
    "rationale": str}. `trace` is accepted for future use (e.g. referencing
    a healed chart or a dropped approach) but is not yet used in the prompt.

    Falls back to a generic title (never blank) if the model doesn't return
    parseable JSON — a bad title shouldn't fail the whole agent run.
    """
    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        goal=goal or "(none set)",
        charts_summary=_summarize_charts_for_rationale(charts_built),
    )
    raw = (await generate(prompt, stage="rationale")).strip()

    try:
        parsed = json.loads(raw)
        dashboard_title = (parsed.get("dashboard_title") or "").strip() or "Agent-Built Dashboard"
        rationale = (parsed.get("rationale") or "").strip()
        return {"dashboard_title": dashboard_title, "rationale": rationale}
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Synthesis step returned non-JSON output — falling back to raw text as rationale")
        return {"dashboard_title": "Agent-Built Dashboard", "rationale": raw}


async def stream_agent(
    goal: str,
    table_name: str,
    field_map: dict,
    semantics: dict,
    profile: dict,
    pool,
    existing_charts: list | None = None,
) -> AsyncGenerator[dict, None]:

    agent_charts = [c for c in (existing_charts or []) if c.get("source") != "user"]
    locked_charts = [c for c in (existing_charts or []) if c.get("source") == "user"]

    field_reference = _build_field_reference(field_map, semantics)
    profile_summary = _build_profile_summary(profile)
    existing_charts_section = _build_existing_charts_section(agent_charts )
    has_existing_charts = bool(existing_charts)

    has_country = bool(semantics.get("country"))
    chart_type_guidance = CHART_TYPE_GUIDANCE
    if has_country:
        chart_type_guidance = CHART_TYPE_GUIDANCE + MAP_GUIDANCE

    system_content = SYSTEM_PROMPT.format(
        table_name=table_name,
        field_reference=field_reference,
        profile_summary=profile_summary,
        existing_charts_section=existing_charts_section,
        goal=goal,
        chart_type_guidance=chart_type_guidance,
    )

    messages = [{"role": "user", "content": system_content}]
    charts_built = list(existing_charts) if existing_charts else []
    inspect_count = 0

    async def execute_sql_fn(sql: str) -> dict:
        from app.services.queryExecutor import execute_raw_query
        return await execute_raw_query(pool, sql, table_name)

    for iteration in range(settings.AGENT_MAX_ITERATIONS):
        available_tools = _get_available_tools(inspect_count, has_existing_charts, has_country)
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

            synthesis = await generate_dashboard_synthesis(goal, charts_built, [])
            quota = await get_current_user_quota()

            yield {
                "type": "rationale",
                "step": iteration + 1,
                "tool": "finish",
                "quota": quota,
                "dashboard_title": synthesis["dashboard_title"],
                "text": synthesis["rationale"],
            }
            yield {
                "type": "finish",
                "step": iteration + 1,
                "tool": "finish",
                "reasoning": summary,
                "observation": observation,
                "charts_built": charts_built + locked_charts,
            }
            break

        if tool_name == "inspect_data":
            observation, trace_entry = await dispatch_inspect_data(
                tool_args=tool_args, execute_sql_fn=execute_sql_fn, step=iteration + 1, table_name=table_name,
            )
            inspect_count += 1
            yield {"type": "inspect_result", **trace_entry}

        elif tool_name == "build_and_add_chart":
            observation, trace_entry, healed = await dispatch_build_and_add_chart(
            tool_args=tool_args, pool=pool, field_map=field_map,
            charts_built=charts_built, step=iteration + 1, table_name=table_name,
            profile=profile, semantics=semantics,)
            if healed:
                yield {"type": "healing", "step": iteration + 1, "chart_title": tool_args.get("chart_title", "")}
            yield {"type": "chart_built" if observation.get("success") else "chart_failed", **trace_entry}

        elif tool_name == "edit_existing_chart":
            observation, trace_entry, healed = await dispatch_edit_existing_chart(
                tool_args=tool_args, pool=pool, field_map=field_map,
                charts_built=charts_built, step=iteration + 1, table_name=table_name,
                profile=profile,semantics=semantics,)
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
            quota = await get_current_user_quota()
            yield {"type": "phase_error","quota": quota, **trace_entry}

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
    rationale = ""
    dashboard_title = ""

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

        if event_type == "rationale":
            rationale = event.get("text", "")
            dashboard_title = event.get("dashboard_title", "")
            continue

        if event_type not in ("step_started", "healing"):
            trace_entry = {k: v for k, v in event.items() if k not in ("type", "charts_built")}
            trace.append(trace_entry)

    return {
        "charts_built": charts_built,
        "trace": trace,
        "rationale": rationale,
        "dashboard_title": dashboard_title,
    }