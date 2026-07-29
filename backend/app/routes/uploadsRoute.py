import hashlib
from pathlib import Path
from uuid import uuid4
from app.config import settings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.services.csvLoader import load_csv_to_postgres, sanitise_table_name
from app.services.database import (
    persist_dataset_metadata,
    get_dataset_metadata,
    get_dataset_by_checksum,
    delete_dataset,
    get_dataset_owner,
    list_datasets_for_user
)
from app.dependencies import get_db, require_editor, get_current_user

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    comment: str | None = Form(None),
    replace: bool = False,
    force_new: bool = False,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing Filename")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files supported")

    # Read bytes early — needed for checksum before any conflict checks
    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()

    # Filename-based conflict check
    existing = None
    for f in UPLOAD_DIR.glob("*.csv"):
        if f.name.split("_", 1)[-1] == file.filename:
            candidate_id = f.name.split("_", 1)[0]
            owner = await get_dataset_owner(db, candidate_id)
            if owner == current_user.user_id:
                existing = f
                break

    if existing and not replace and not force_new:
        existing_dataset_id = existing.name.split("_", 1)[0]
        raise HTTPException(
            status_code=409,
            detail={"conflict": True, "existing_dataset_id": existing_dataset_id},
        )

    # Checksum-based conflict check — catches identical content under a different filename
    if not replace and not force_new:
        duplicate_id = await get_dataset_by_checksum(db, checksum, current_user.user_id)
        if duplicate_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "conflict": True,
                    "existing_dataset_id": duplicate_id,
                    "reason": "duplicate_content",
                },
            )

    if existing and replace:
        existing_dataset_id = existing.name.split("_", 1)[0]
        metadata = await get_dataset_metadata(db, existing_dataset_id)
        if metadata:
            await delete_dataset(db, existing_dataset_id, metadata["table_name"])
        existing.unlink(missing_ok=True)

    dataset_id = str(uuid4())
    safe_name = f"{dataset_id}_{Path(file.filename).name}"
    save_path = UPLOAD_DIR / safe_name

    save_path.write_bytes(content)

    table_name = sanitise_table_name(file.filename)

    try:
        load_result = await load_csv_to_postgres(db, save_path, table_name)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load CSV into Postgres: {str(e)}"
        )

    # field_map now comes straight from the load result — col_types was
    # already computed while creating the table, same base_type shape
    # Metabase's sync used to return.
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

    return {
        "dataset_id": dataset_id,
        "original_filename": file.filename,
        "table_name": table_name,
        "row_count": load_result["row_count"],
        "field_map": field_map,
        "name": name,
        "comment": comment,
    }


@router.get("/datasets")
async def list_datasets(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    datasets = await list_datasets_for_user(db, current_user.user_id)
    return {
        "datasets": [
            {
                "dataset_id": d["dataset_id"],
                "original_filename": d["original_filename"],
                "name": d["name"],
            }
            for d in datasets
        ]
    }
