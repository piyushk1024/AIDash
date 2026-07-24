import hashlib
import json
import logging
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.dependencies import get_db, require_editor
from app.services.csvLoader import load_csv_to_postgres, sanitise_table_name
from app.services.profiler import profile_csv
from app.services.llmClient import infer_semantics_with_llm
from app.services.pipelineOrchestrator import stream_pipeline
from app.services.agentOrchestrator import stream_agent
from app.services.llm import LLMUnavailableError
from app.services.database import (
    persist_dataset_metadata,
    persist_profile_json,
    persist_semantics,
    persist_dashboard_plan,
    update_dashboard_plan,
    json_default,
)

router = APIRouter()
logger = logging.getLogger(__name__)
UPLOAD_DIR = settings.UPLOAD_DIR

DEFAULT_AGENT_GOAL = "Build the most analytically interesting dashboard you can from this dataset."


def _sse_format(event: dict) -> str:
    return f"data: {json.dumps(event, default=json_default)}\n\n"


@router.post("/datasets/launch/stream")
async def launch_dataset_stream(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    comment: str | None = Form(None),
    mode: str = Form("pipeline"),
    hint: str | None = Form(None),
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    if mode not in ("pipeline", "agent"):
        raise HTTPException(status_code=400, detail="mode must be 'pipeline' or 'agent'")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files supported")

    # Upload — no conflict-checking here (per the dropped replace/rename
    # flow); dashboard name is the disambiguator now, every launch is a new
    # dataset_id.
    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()
    dataset_id = str(uuid4())
    safe_name = f"{dataset_id}_{Path(file.filename).name}"
    save_path = UPLOAD_DIR / safe_name
    save_path.write_bytes(content)

    table_name = sanitise_table_name(file.filename)
    try:
        load_result = await load_csv_to_postgres(db, save_path, table_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load CSV into Postgres: {str(e)}")

    field_map = {col: {"base_type": base_type} for col, base_type in load_result["columns"].items()}

    await persist_dataset_metadata(
        db,
        dataset_id=dataset_id,
        table_name=table_name,
        field_map=field_map,
        user_id=current_user.user_id,
        name=name,
        comment=comment,
        original_filename=file.filename,
        file_checksum=checksum,
    )

    async def event_generator():
        yield _sse_format({
            "type": "dataset_created",
            "dataset_id": dataset_id,
            "row_count": load_result["row_count"],
        })

        try:
            if mode == "pipeline":
                async for event in stream_pipeline(
                    file_path=save_path,
                    dataset_id=dataset_id,
                    table_name=table_name,
                    field_map=field_map,
                    business_hint=hint,
                    pool=db,
                ):
                    phase = event.get("phase")
                    if event["type"] == "step_done" and phase == "profile":
                        await persist_profile_json(db, dataset_id, event["profile"])
                    elif event["type"] == "step_done" and phase == "semantics":
                        await persist_semantics(db, dataset_id, hint, event["semantics"])
                    elif event["type"] == "step_done" and phase == "plan":
                        await persist_dashboard_plan(db, dataset_id, event["plan"])
                    elif event["type"] == "finish":
                        await update_dashboard_plan(db, dataset_id, event["plan"], mode="pipeline")

                    yield _sse_format(event)

            else:  # agent
                yield _sse_format({"type": "step_started", "phase": "profile"})
                profile = await run_in_threadpool(profile_csv, save_path, dataset_id)
                await persist_profile_json(db, dataset_id, profile)
                yield _sse_format({"type": "step_done", "phase": "profile"})

                yield _sse_format({"type": "step_started", "phase": "semantics"})
                semantics_result = await infer_semantics_with_llm(dataset_profile=profile, business_hint=hint)
                semantics = semantics_result.model_dump()
                await persist_semantics(db, dataset_id, hint, semantics)
                yield _sse_format({"type": "step_done", "phase": "semantics"})

                goal = (hint or "").strip() or DEFAULT_AGENT_GOAL
                charts_built, trace = [], []
                agent_plan = {
                    "dataset_id": dataset_id,
                    "mode": "agent",
                    "goal": goal,
                    "charts": charts_built,
                    "trace": trace,
                    "rationale": "",
                    "dashboard_title": "",
                }
                await persist_dashboard_plan(db, dataset_id, agent_plan)

                yield _sse_format({"type": "step_started", "phase": "build"})

                async for event in stream_agent(
                    goal=goal,
                    table_name=table_name,
                    field_map=field_map,
                    semantics=semantics,
                    profile=profile,
                    pool=db,
                    existing_charts=None,
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
                        })
                    elif event_type == "rationale":
                        agent_plan = {
                            **agent_plan,
                            "rationale": event.get("text", ""),
                            "dashboard_title": event.get("dashboard_title", ""),
                        }
                        await update_dashboard_plan(db, dataset_id, agent_plan, mode="agent")
                        yield _sse_format(event)
                        continue

                    if event_type not in ("step_started", "healing"):
                        trace_entry = {k: v for k, v in event.items() if k not in ("type", "charts_built")}
                        trace.append(trace_entry)
                        agent_plan = {**agent_plan, "charts": charts_built, "trace": trace}
                        await update_dashboard_plan(db, dataset_id, agent_plan, mode="agent")

                    yield _sse_format(event)

        except LLMUnavailableError as e:
            logger.exception("Launch stream failed for dataset %s — LLM unavailable", dataset_id)
            yield _sse_format({
                "type": "phase_error",
                "error": f"AI provider ({e.provider}) is currently unavailable. Please try again shortly.",
            })
        except Exception:
            logger.exception("Launch stream failed for dataset %s", dataset_id)
            yield _sse_format({
                "type": "phase_error",
                "error": "Launch failed. Please try again.",
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