from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.services.database import get_dataset_metadata, delete_dataset
from app.services.metabaseClient import get_session_token, delete_dashboard, delete_card, get_dashboard_card_ids

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

@router.delete("/datasets/{dataset_id}")
async def delete_dataset_by_id(dataset_id: str):
    metadata = get_dataset_metadata(dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Delete Metabase dashboard if one was created    
    dashboard_id = metadata.get("metabase_dashboard_id")
    if dashboard_id:
        try:
            token = get_session_token()
            card_ids = get_dashboard_card_ids(token, dashboard_id)
            delete_dashboard(token, dashboard_id)
            for card_id in card_ids:
                delete_card(token, card_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Metabase cleanup failed: {str(e)}")

    # Delete uploaded CSV file
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    for f in matches:
        f.unlink(missing_ok=True)

    # Delete Postgres table and all metadata rows
    delete_dataset(dataset_id, metadata["table_name"])

    return {"deleted": dataset_id}