import logging
# from pathlib import Path
from typing import AsyncGenerator
# from starlette.concurrency import run_in_threadpool
from app.services.profiler import profile_csv
from app.services.llmClient import infer_semantics_with_llm
from app.services.dashboardPlanner import generate_dashboard_plan
from app.services.cardBuilder import build_card_with_healing
from app.services.llm import is_llm_in_cooldown, LLMUnavailableError
from app.services.quotaGuard import QuotaExceededError
from app.schemas.chartTypes import CHART_TYPE_VALUES
from app.services.quotaGuard import get_current_user_quota

logger = logging.getLogger(__name__)


def _validate_and_clean_charts(charts: list) -> list:
    # Same dedup/validation as dashboardRoute.validate_and_clean_charts —
    # duplicated here rather than imported to keep this file's only
    # dependency on dashboardRoute at zero (route stays a thin caller).
    seen_titles = set()
    cleaned = []
    for chart in charts:
        if not chart.get("sql") or not chart.get("chart_title") or not chart.get("chart_type"):
            continue
        if chart["chart_type"] not in CHART_TYPE_VALUES:
            continue
        if chart["chart_title"] in seen_titles:
            continue
        seen_titles.add(chart["chart_title"])
        cleaned.append(chart)
    return cleaned


async def stream_pipeline(    
    dataset_id: str,
    table_name: str,
    field_map: dict,
    business_hint: str | None,
    pool,
) -> AsyncGenerator[dict, None]:
    """
    Runs profile -> semantics -> plan -> build as one chained flow for the
    one-shot launch route, yielding progress events. Event shape
    (step_started/chart_built/chart_failed/finish) mirrors stream_agent so
    the frontend can share a renderer across both modes. Does not persist
    anything itself — caller persists after each event, same split as
    stream_agent/run_agent_dashboard_stream.
    """
    # ── Phase 1: profile ──
    yield {"type": "step_started", "phase": "profile"}
    profile = await profile_csv(pool, table_name, dataset_id)
    yield {"type": "step_done", "phase": "profile", "profile": profile}

    # ── Phase 2: semantics ──
    yield {"type": "step_started", "phase": "semantics"}
    try:
        semantics_result = await infer_semantics_with_llm(
            dataset_profile=profile, business_hint=business_hint
        )
    except LLMUnavailableError as e:
        yield {
            "type": "phase_error",
            "phase": "semantics",
            "error": f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.",
        }
        return
    except QuotaExceededError:
        yield {
            "type": "phase_error",
            "phase": "semantics",
            "error": "Daily demo limit reached. Please try again tomorrow.",
        }
        return
    semantics = semantics_result.model_dump()
    yield {"type": "step_done", "phase": "semantics", "semantics": semantics}

    # ── Phase 3: plan ──
    yield {"type": "step_started", "phase": "plan"}
    try:
        plan = await generate_dashboard_plan(dataset_id, semantics, profile, table_name, field_map)
    except LLMUnavailableError as e:
        yield {
            "type": "phase_error",
            "phase": "plan",
            "error": f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.",
        }
        return
    except QuotaExceededError:
        yield {
            "type": "phase_error",
            "phase": "plan",
            "error": "Daily demo limit reached. Please try again tomorrow.",
        }
        return

    plan["charts"] = _validate_and_clean_charts(plan["charts"])
    if not plan["charts"]:
        yield {
            "type": "phase_error",
            "phase": "plan",
            "error": "No valid charts could be generated. Try re-running with a different hint.",
        }
        return
    plan["mode"] = "pipeline"
    yield {"type": "step_done", "phase": "plan", "plan": plan}

    # ── Phase 4: build ──
    yield {"type": "step_started", "phase": "build"}
    built_charts, errors = [], []
    provider_unavailable = False

    for chart in plan["charts"]:
        if provider_unavailable:
            error = {
                "chart_title": chart.get("chart_title"),
                "chart_type": chart.get("chart_type"),
                "failed": True,
                "skipped": True,
                "reason": "AI provider rate-limited — skipped, remaining charts not attempted. Retry shortly.",
            }
            errors.append(error)
            yield {"type": "chart_failed", "chart_title": chart.get("chart_title"), "error": error}
            continue

        result, error = await build_card_with_healing(
            chart, field_map, pool, table_name, existing_id=chart.get("card_id"),
        )

        if error:
            errors.append(error)
            if is_llm_in_cooldown():
                provider_unavailable = True
            yield {"type": "chart_failed", "chart_title": chart.get("chart_title"), "error": error}
            continue

        built = {**chart, **result}
        built_charts.append(built)
        yield {
            "type": "chart_built",
            "chart_title": built.get("chart_title"),
            "chart_type": built.get("chart_type"),
            "card_id": built.get("card_id"),
            "healed": built.get("healed", False),
            "rows": built.get("rows"),
            "spec": built.get("spec"),
        }

    final_plan = {**plan, "charts": built_charts, "errors": errors}
    quota = await get_current_user_quota()
    yield {
        "type": "finish",        
        "charts_built": built_charts,
        "errors": errors,
        "plan": final_plan,
        "quota": quota,
    }