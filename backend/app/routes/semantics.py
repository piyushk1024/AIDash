import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from app.schemas.semantics import (
    InferSemanticsRequest,
    InferSemanticsResponse,
)
from app.services.profiler import profile_csv
from app.services.llmClient import infer_semantics_with_llm

router = APIRouter()

UPLOAD_DIR = Path("app/uploads")


@router.post(
    "/infer-dataset-semantics/{dataset_id}", response_model=InferSemanticsResponse
)
async def infer_dataset_semantics(dataset_id: str, payload: InferSemanticsRequest):
    matched_files = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matched_files:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = matched_files[0]
    profile = profile_csv(file_path, dataset_id=dataset_id)

    result = infer_semantics_with_llm(
        dataset_profile=profile, business_hint=payload.business_hint
    )

    return result
