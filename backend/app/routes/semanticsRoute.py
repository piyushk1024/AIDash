import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from app.schemas.semantics import (
    InferSemanticsRequest,
    InferSemanticsResponse,
)
from app.services.profiler import profile_csv
from app.services.database import get_cached_semantics, persist_semantics
from app.services.llmClient import infer_semantics_with_llm
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

@router.post("/infer-dataset-semantics/{dataset_id}", response_model=InferSemanticsResponse)
async def infer_dataset_semantics(dataset_id: str, payload: InferSemanticsRequest):
    matched_files = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matched_files:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Check cache first
    cached = get_cached_semantics(dataset_id)
    if cached:
        return InferSemanticsResponse(**cached)

    # Run inference
    file_path = matched_files[0]
    profile = profile_csv(file_path, dataset_id=dataset_id)
    result = infer_semantics_with_llm(
        dataset_profile=profile, business_hint=payload.business_hint
    )

    # Persist result
    persist_semantics(dataset_id, payload.business_hint, result.model_dump())

    return result


# @router.post("/infer-dataset-semantics/{dataset_id}", response_model=InferSemanticsResponse)
# async def infer_dataset_semantics(dataset_id: str, payload: InferSemanticsRequest):
#     matched_files = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
#     if not matched_files:
#         raise HTTPException(status_code=404, detail="Dataset not found")

#     file_path = matched_files[0]
#     profile = profile_csv(file_path, dataset_id=dataset_id)

#     result = infer_semantics_with_llm(
#         dataset_profile=profile, business_hint=payload.business_hint
#     )
#     return result
