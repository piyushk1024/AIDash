from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from app.config import settings
from app.services.profiler import profile_csv
from app.dependencies import get_current_user



router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR

@router.get("/profile-csv/{dataset_id}")
async def profile_csv_route(dataset_id: str, current_user=Depends(get_current_user)):
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return profile_csv(matches[0], dataset_id)