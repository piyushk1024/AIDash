from pathlib import Path
from uuid import uuid4, UUID
from app.config import settings
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.services.csvLoader import load_csv_to_postgres, sanitise_table_name
from app.services.database import (
    persist_dataset_metadata,
    get_dataset_metadata,
    delete_dataset,
    get_dataset_owner
)
from app.services.metabaseClient import (
    get_session_token,
    trigger_metabase_sync,
    fetch_field_map_for_table,
    get_database_id,
    delete_dashboard,
    delete_card,
    get_dashboard_card_ids,
)
from app.dependencies import get_db, get_http_client, get_app_state, require_editor, get_current_user

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    replace: bool = False,
    force_new: bool = False,
    db=Depends(get_db),
    http_client=Depends(get_http_client),
    app_state=Depends(get_app_state),
    current_user=Depends(require_editor),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing Filename")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files supported")

    existing = next(
        (
            f
            for f in UPLOAD_DIR.glob("*.csv")
            if f.name.split("_", 1)[-1] == file.filename
        ),
        None,
    )
    if existing and not replace and not force_new:
        existing_dataset_id = existing.name.split("_", 1)[0]
        raise HTTPException(
            status_code=409,
            detail={"conflict": True, "existing_dataset_id": existing_dataset_id},
        )

    if existing and replace:
        existing_dataset_id = existing.name.split("_", 1)[0]
        metadata = await get_dataset_metadata(db, existing_dataset_id)
        if metadata:
            dashboard_id = metadata.get("metabase_dashboard_id")
            if dashboard_id:
                try:
                    token = await get_session_token(http_client, app_state)
                    card_ids = await get_dashboard_card_ids(token, http_client, dashboard_id)
                    await delete_dashboard(token, http_client, dashboard_id)
                    for card_id in card_ids:
                        await delete_card(token, http_client, card_id)
                except Exception:
                    pass
            await delete_dataset(db, existing_dataset_id, metadata["table_name"])
        existing.unlink(missing_ok=True)

    dataset_id = str(uuid4())
    safe_name = f"{dataset_id}_{Path(file.filename).name}"
    save_path = UPLOAD_DIR / safe_name

    content = await file.read()
    save_path.write_bytes(content)

    table_name = sanitise_table_name(file.filename)

    try:
        load_result = await load_csv_to_postgres(db, save_path, table_name)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load CSV into Postgres: {str(e)}"
        )

    try:
        token = await get_session_token(http_client, app_state)
        database_id = await get_database_id(token, http_client)
        await trigger_metabase_sync(token, http_client, database_id)
        metabase_result = await fetch_field_map_for_table(token, http_client, table_name, database_id)
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metabase sync failed: {str(e)}")

    await persist_dataset_metadata(
        db,
        dataset_id=dataset_id,
        table_name=table_name,
        metabase_table_id=metabase_result["table_id"],
        field_map=metabase_result["field_map"],
        user_id=current_user.user_id,
    )

    return {
        "dataset_id": dataset_id,
        "original_filename": file.filename,
        "table_name": table_name,
        "row_count": load_result["row_count"],
        "metabase_table_id": metabase_result["table_id"],
        "field_map": metabase_result["field_map"],
    }


@router.get("/datasets")
async def list_datasets(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
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

        owner = await get_dataset_owner(db, dataset_id)
        if owner != current_user.user_id:
            continue

        datasets.append(
            {
                "dataset_id": dataset_id,
                "original_filename": original_filename,
                "saved_filename": name,
            }
        )

    return {"datasets": datasets}

