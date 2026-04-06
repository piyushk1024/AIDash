from pathlib import Path
from uuid import uuid4, UUID
from app.config import settings
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.services.csvLoader import load_csv_to_postgres, sanitise_table_name
from app.services.metabaseClient import get_session_token, trigger_metabase_sync, fetch_field_map_for_table
from app.services.database import persist_dataset_metadata

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

    table_name = sanitise_table_name(file.filename)

    try:
        load_result = load_csv_to_postgres(save_path, table_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load CSV into Postgres: {str(e)}")

    try:
        token = get_session_token()
        trigger_metabase_sync(token)
        metabase_result = fetch_field_map_for_table(token, table_name)
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metabase sync failed: {str(e)}")

    persist_dataset_metadata(
        dataset_id=dataset_id,
        table_name=table_name,
        metabase_table_id=metabase_result["table_id"],
        field_map=metabase_result["field_map"]
    )

    return {
        "dataset_id": dataset_id,
        "original_filename": file.filename,
        "table_name": table_name,
        "row_count": load_result["row_count"],
        "metabase_table_id": metabase_result["table_id"],
        "field_map": metabase_result["field_map"]
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

        datasets.append({
            "dataset_id": dataset_id,
            "original_filename": original_filename,
            "saved_filename": name,
        })

    return {"datasets": datasets}