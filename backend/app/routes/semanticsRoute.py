
from fastapi import APIRouter, HTTPException, Depends, Query
from app.schemas.semantics import (
    InferSemanticsRequest,
    InferSemanticsResponse,
)
from app.dependencies import get_db, require_editor
from app.services.profiler import profile_csv
from app.services.database import (
    get_cached_semantics,
    get_cached_profile,
    persist_semantics,
    get_dataset_owner,
    mark_plan_stale,
)
from app.services.llmClient import infer_semantics_with_llm
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR


@router.post("/infer-dataset-semantics/{dataset_id}", response_model=InferSemanticsResponse)
async def infer_dataset_semantics(
    dataset_id: str,
    payload: InferSemanticsRequest,
    force: bool = Query(False),
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    owner = await get_dataset_owner(db, dataset_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    cached = await get_cached_semantics(db, dataset_id)

    hint_changed = cached and (cached["business_hint"] != payload.business_hint)
    should_rerun = force or not cached or hint_changed

    if not should_rerun:
        return InferSemanticsResponse(**cached["semantics_json"])

    # Get profile from cache or compute from file
    profile = await get_cached_profile(db, dataset_id)
    if not profile:
        matched_files = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
        if not matched_files:
            raise HTTPException(status_code=404, detail="Dataset file not found")
        profile = profile_csv(matched_files[0], dataset_id=dataset_id)

    result = await infer_semantics_with_llm(
        dataset_profile=profile, business_hint=payload.business_hint
    )

    await persist_semantics(db, dataset_id, payload.business_hint, result.model_dump())

    # Hint changed — downstream plan is now derived from outdated semantics
    if hint_changed:
        await mark_plan_stale(db, dataset_id)

    return result