import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.database import (
    get_cached_semantics,
    get_dataset_metadata,
    get_dataset_owner,
    persist_dashboard_plan,
    update_dashboard_plan,
    persist_profile_json,
)
from app.services.profiler import profile_csv
from app.services.agentOrchestrator import run_agent, stream_agent
from app.services.llm import LLMUnavailableError
from app.dependencies import get_db, require_editor
from app.config import settings
import logging

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR


logger = logging.getLogger(__name__)

DEFAULT_GOAL = "Build the most analytically interesting dashboard you can from this dataset."


class AgentRequest(BaseModel):
    goal: str = DEFAULT_GOAL


async def _setup_agent_run(dataset_id, db, current_user, goal_raw):
    """
    Shared setup for both the sync and streaming agent routes: auth/ownership
    checks, dataset file + metadata lookup, profiling. Pipeline and agent
    dashboards now coexist independently (each is its own dashboard_plans
    row, scoped by mode) — no shared dashboard resource to check or clear
    before starting a run. Raises HTTPException on any failure — caller
    does not need to wrap this in try/except.
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

    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found.")

    profile = profile_csv(matches[0], dataset_id)
    await persist_profile_json(db, dataset_id, profile)

    goal = (goal_raw or "").strip() or DEFAULT_GOAL

    return {
        "semantics": semantics,
        "metadata": metadata,
        "profile": profile,
        "goal": goal,
    }


@router.post("/datasets/{dataset_id}/dashboard/agent")
async def run_agent_dashboard(
    dataset_id: str,
    body: AgentRequest,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    try:
        setup = await _setup_agent_run(dataset_id, db, current_user, body.goal)

        result = await run_agent(
            goal=setup["goal"],
            table_name=setup["metadata"]["table_name"],
            field_map=setup["metadata"]["field_map"],
            semantics=setup["semantics"]["semantics_json"],
            profile=setup["profile"],
            pool=db,
        )

        agent_plan = {
            "dataset_id": dataset_id,
            "mode": "agent",
            "goal": setup["goal"],
            "charts": result["charts_built"],
            "trace": result["trace"],
        }
        await persist_dashboard_plan(db, dataset_id, agent_plan)

        return {
            "charts_built": result["charts_built"],
            "trace": result["trace"],
        }

    except HTTPException:
        raise
    except LLMUnavailableError as e:
        logger.exception("Agent run failed for dataset %s — LLM unavailable", dataset_id)
        raise HTTPException(status_code=503, detail=f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.")
    except Exception:
        logger.exception("Agent run failed for dataset %s", dataset_id)
        raise HTTPException(status_code=500, detail="Agent run failed. Please try again.")


def _sse_format(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@router.post("/datasets/{dataset_id}/dashboard/agent/stream")
async def run_agent_dashboard_stream(
    dataset_id: str,
    body: AgentRequest,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    # All setup that can fail with a clean HTTP status runs before the stream
    # opens, so the client gets a normal 404/403/etc rather than a swallowed
    # error mid-stream.
    setup = await _setup_agent_run(dataset_id, db, current_user, body.goal)

    async def event_generator():
        charts_built = []
        trace = []

        # Insert the row now so a disconnect right after starting still
        # leaves a recoverable row for GET /datasets/{id}/state.
        agent_plan = {
            "dataset_id": dataset_id,
            "mode": "agent",
            "goal": setup["goal"],
            "charts": charts_built,
            "trace": trace,
        }
        await persist_dashboard_plan(db, dataset_id, agent_plan)

        try:
            async for event in stream_agent(
                goal=setup["goal"],
                table_name=setup["metadata"]["table_name"],
                field_map=setup["metadata"]["field_map"],
                semantics=setup["semantics"]["semantics_json"],
                profile=setup["profile"],
                pool=db,
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
                    })

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