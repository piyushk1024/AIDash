import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from app.schemas.semantics import (
    InferSemanticsRequest,
    InferSemanticsResponse,
)
from app.dependencies import get_db, require_editor
from app.services.profiler import profile_csv
from app.services.database import get_cached_semantics, persist_semantics, get_dataset_owner
from app.services.llmClient import infer_semantics_with_llm
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

@router.post("/infer-dataset-semantics/{dataset_id}", response_model=InferSemanticsResponse)
async def infer_dataset_semantics(dataset_id: str, payload: InferSemanticsRequest, db=Depends(get_db), current_user=Depends(require_editor)):
    matched_files = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matched_files:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check cache first
    cached = await get_cached_semantics(db, dataset_id)
    if cached:
        return InferSemanticsResponse(**cached)

    # Run inference
    file_path = matched_files[0]
    profile = profile_csv(file_path, dataset_id=dataset_id)
    result = await infer_semantics_with_llm(
        dataset_profile=profile, business_hint=payload.business_hint
    )

    # Persist result
    await persist_semantics(db, dataset_id, payload.business_hint, result.model_dump())

    return result