from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.services.profiler import profile_csv

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR

@router.get("/profile-csv/{dataset_id}")
def profile_csv_route(dataset_id: str):
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    file_path = matches[0]
    return profile_csv(file_path, dataset_id)