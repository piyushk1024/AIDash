import json
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.database import (
    get_cached_semantics,
    get_cached_dashboard_plan,
    get_dataset_metadata,
    get_dataset_owner,
    persist_dashboard_plan,
    update_dashboard_plan,
    persist_profile_json,
    set_last_active_mode
)

from app.services.profiler import profile_csv
from app.services.agentOrchestrator import run_agent, stream_agent
from app.services.reportGenerator import generate_agent_report_pdf
from app.services.llm import LLMUnavailableError
from app.dependencies import get_db, get_current_user, require_editor

from starlette.concurrency import run_in_threadpool
import logging

router = APIRouter()



logger = logging.getLogger(__name__)

DEFAULT_GOAL = "Build the most analytically interesting dashboard you can from this dataset."


class AgentRequest(BaseModel):
    goal: str = DEFAULT_GOAL
    nudge: bool = False


async def _setup_agent_run(dataset_id, db, current_user, goal_raw, nudge):
    """
    Shared setup for both the sync and streaming agent routes: auth/ownership
    checks, dataset file + metadata lookup, profiling, and — for a nudge —
    loading the existing agent-mode dashboard to build on. Raises
    HTTPException on any failure — caller does not need to wrap this in
    try/except.
    """
    semantics = await get_cached_semantics(db, dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")

    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    profile = await profile_csv(db, metadata["table_name"], dataset_id)
    await persist_profile_json(db, dataset_id, profile)

    goal = (goal_raw or "").strip() or DEFAULT_GOAL

    existing_charts = None
    existing_trace = []
    existing_rationale = ""
    existing_dashboard_title = ""
    cache_hit = False
    if nudge:
        existing_plan = await get_cached_dashboard_plan(db, dataset_id, mode="agent")
        if not existing_plan or not existing_plan.get("charts"):
            raise HTTPException(
                status_code=400,
                detail="No existing agent dashboard found to nudge. Run without nudge first.",
            )
        existing_charts = existing_plan["charts"]
        existing_trace = existing_plan.get("trace", [])
        existing_rationale = existing_plan.get("rationale", "")
        existing_dashboard_title = existing_plan.get("dashboard_title", "")
        cache_hit = existing_plan.get("goal") == goal

    return {
        "semantics": semantics,
        "metadata": metadata,
        "profile": profile,
        "goal": goal,
        "existing_charts": existing_charts,
        "existing_trace": existing_trace,
        "existing_rationale": existing_rationale,
        "existing_dashboard_title": existing_dashboard_title,
        "cache_hit": cache_hit
    }


@router.post("/datasets/{dataset_id}/dashboard/agent")
async def run_agent_dashboard(
    dataset_id: str,
    body: AgentRequest,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    try:
        setup = await _setup_agent_run(dataset_id, db, current_user, body.goal, body.nudge)

        if setup["cache_hit"]:
            # Goal unchanged since the last nudge — nothing to build, skip
            # the LLM call and return the existing agent dashboard as-is.
            await set_last_active_mode(db, dataset_id, "agent")
            return {
                "charts_built": setup["existing_charts"],
                "trace": setup["existing_trace"],
                "rationale": setup["existing_rationale"],
                "dashboard_title": setup["existing_dashboard_title"],
                "cached": True,
            }

        result = await run_agent(
            goal=setup["goal"],
            table_name=setup["metadata"]["table_name"],
            field_map=setup["metadata"]["field_map"],
            semantics=setup["semantics"]["semantics_json"],
            profile=setup["profile"],
            pool=db,
            existing_charts=setup["existing_charts"],
        )

        combined_trace = setup["existing_trace"] + result["trace"]

        agent_plan = {
            "dataset_id": dataset_id,
            "mode": "agent",
            "goal": setup["goal"],
            "charts": result["charts_built"],
            "trace": combined_trace,
            "rationale": result["rationale"],
            "dashboard_title": result["dashboard_title"],
        }

        if body.nudge:
            await update_dashboard_plan(db, dataset_id, agent_plan)
        else:
            await persist_dashboard_plan(db, dataset_id, agent_plan)
        await set_last_active_mode(db, dataset_id, "agent")

        return {
            "charts_built": result["charts_built"],
            "trace": combined_trace,
            "rationale": result["rationale"],
            "dashboard_title": result["dashboard_title"],
        }

    except HTTPException:
        raise
    except LLMUnavailableError as e:
        logger.exception("Agent run failed for dataset %s — LLM unavailable", dataset_id)
        raise HTTPException(status_code=503, detail=f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.")
    except Exception:
        logger.exception("Agent run failed for dataset %s", dataset_id)
        raise HTTPException(status_code=500, detail="Agent run failed. Please try again.")


class ChartImage(BaseModel):
    chart_title: str
    image_base64: str  # PNG, base64-encoded, no "data:image/png;base64," prefix


class ReportRequest(BaseModel):
    charts: list[ChartImage]

@router.post("/datasets/{dataset_id}/report")
async def get_agent_dashboard_report(
    dataset_id: str,
    body: ReportRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    agent_plan = await get_cached_dashboard_plan(db, dataset_id, mode="agent")
    if not agent_plan or not agent_plan.get("charts"):
        raise HTTPException(status_code=404, detail="No agent-built dashboard found for this dataset.")

    if not body.charts:
        raise HTTPException(status_code=400, detail="No chart images provided.")

    metadata = await get_dataset_metadata(db, dataset_id)
    fallback_title = (metadata or {}).get("original_filename", "Dashboard Report")
    dashboard_title = agent_plan.get("dashboard_title") or fallback_title

    pdf_bytes = await run_in_threadpool(
        generate_agent_report_pdf,
        dashboard_title=dashboard_title,
        rationale=agent_plan.get("rationale", ""),
        charts=[c.model_dump() for c in body.charts],
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}_report.pdf"'},
    )

def _sse_format(event: dict) -> str:
    from app.services.database import json_default
    return f"data: {json.dumps(event, default=json_default)}\n\n"


@router.post("/datasets/{dataset_id}/dashboard/agent/stream")
async def run_agent_dashboard_stream(
    dataset_id: str,
    body: AgentRequest,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    # All setup that can fail with a clean HTTP status runs before the stream
    # opens, so the client gets a normal 404/403/400/etc rather than a
    # swallowed error mid-stream.
    setup = await _setup_agent_run(dataset_id, db, current_user, body.goal, body.nudge)

    async def event_generator():
        if setup["cache_hit"]:
            # Goal unchanged since the last nudge — skip the LLM call and
            # just replay the existing result as a rationale + finish pair,
            # which is all applyAgentEvents/ProcessingView need to settle.
            await set_last_active_mode(db, dataset_id, "agent")
            yield _sse_format({
                "type": "rationale",
                "text": setup["existing_rationale"],
                "dashboard_title": setup["existing_dashboard_title"],
            })
            yield _sse_format({
                "type": "finish",
                "reasoning": "No changes — goal matches the last run, reused the cached dashboard.",
                "charts_built": setup["existing_charts"],
            })
            return
        # Seed from existing state on a nudge, so a disconnect right after
        # starting still leaves the true current state recoverable, not an
        # empty dashboard.
        charts_built = list(setup["existing_charts"]) if setup["existing_charts"] else []
        trace = list(setup["existing_trace"])
        rationale = setup.get("existing_rationale", "")
        dashboard_title = setup.get("existing_dashboard_title", "")

        agent_plan = {
            "dataset_id": dataset_id,
            "mode": "agent",
            "goal": setup["goal"],
            "charts": charts_built,
            "trace": trace,
            "rationale": rationale,
            "dashboard_title": dashboard_title,
        }

        if body.nudge:
            await update_dashboard_plan(db, dataset_id, agent_plan)
        else:
            await persist_dashboard_plan(db, dataset_id, agent_plan)
        await set_last_active_mode(db, dataset_id, "agent")

        try:
            async for event in stream_agent(
                goal=setup["goal"],
                table_name=setup["metadata"]["table_name"],
                field_map=setup["metadata"]["field_map"],
                semantics=setup["semantics"]["semantics_json"],
                profile=setup["profile"],
                pool=db,
                existing_charts=setup["existing_charts"],
            ):
                event_type = event["type"]

                if event_type == "chart_built":
                    charts_built.append({
                        "card_id": event["card_id"],
                        "chart_title": event["chart_title"],
                        "chart_type": event["chart_type"],
                        "sql": event["sql"],
                        "x_alias": event.get("x_alias"),
                        "y_alias": event.get("y_alias"),
                        "series_alias": event.get("series_alias"),
                        "viz_params": event.get("viz_params"),
                        "healed": event["healed"],
                        "rows": event.get("rows"),
                        "spec": event.get("spec"),
                        "source": "agent",
                    })
                elif event_type == "chart_edited":
                    match_index = next(
                        (i for i, c in enumerate(charts_built) if c.get("card_id") == event["card_id"]), None
                    )
                    edited = {
                        "card_id": event["card_id"],
                        "chart_title": event["chart_title"],
                        "chart_type": event["chart_type"],
                        "sql": event["sql"],
                        "x_alias": event.get("x_alias"),
                        "y_alias": event.get("y_alias"),
                        "series_alias": event.get("series_alias"),
                        "viz_params": event.get("viz_params"),
                        "healed": event["healed"],
                        "rows": event.get("rows"),
                        "spec": event.get("spec"),
                        "source": "agent",
                    }
                    if match_index is not None:
                        charts_built[match_index] = edited
                    else:
                        charts_built.append(edited)
                elif event_type == "chart_deleted":
                    charts_built[:] = [c for c in charts_built if c.get("card_id") != event.get("card_id")]
                elif event_type == "rationale":
                    rationale = event.get("text", "")
                    dashboard_title = event.get("dashboard_title", "")
                    agent_plan = {**agent_plan, "rationale": rationale, "dashboard_title": dashboard_title}
                    await update_dashboard_plan(db, dataset_id, agent_plan)
                    yield _sse_format(event)
                    continue

                # Persist trace-worthy events (everything except UI-only ones)
                # so the dataset state survives a disconnect mid-run.
                if event_type not in ("step_started", "healing"):
                    trace_entry = {k: v for k, v in event.items() if k not in ("type", "charts_built")}
                    trace.append(trace_entry)
                    agent_plan = {**agent_plan, "charts": charts_built, "trace": trace}
                    await update_dashboard_plan(db, dataset_id, agent_plan)

                yield _sse_format(event)

        except LLMUnavailableError as e:
            logger.exception("Agent stream failed for dataset %s — LLM unavailable", dataset_id)
            yield _sse_format({
                "type": "phase_error",
                "error": f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.",
            })
        except Exception:
            logger.exception("Agent stream failed for dataset %s", dataset_id)
            yield _sse_format({
                "type": "phase_error",
                "error": "Agent run failed. Please try again.",
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )