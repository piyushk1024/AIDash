from pathlib import Path
from uuid import uuid4
from uuid import UUID
from app.config import settings

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing Filename")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files supported")

    dataset_id = str(uuid4())
    safe_name = f"{dataset_id}_{Path(file.filename).name}"
    save_path = UPLOAD_DIR / safe_name

    content = await file.read()
    save_path.write_bytes(content)

    return {
        "dataset_id": dataset_id,
        "original_filename": file.filename,
        "saved_filename": safe_name,
        "size_bytes": len(content),
        "content_type": file.content_type,
    }


@router.get("/datasets")
async def list_datasets():
    datasets = []

    for file_path in UPLOAD_DIR.glob("*.csv"):
        name = file_path.name

        if "_" not in name:
            continue

        dataset_id, original_filename = name.split("_", 1)

        try:
            UUID(dataset_id)
        except ValueError:
            continue

        datasets.append(
            {
                "dataset_id": dataset_id,
                "original_filename": original_filename,
                "saved_filename": name,
            }
        )

    return {"datasets": datasets}
