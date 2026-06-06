from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import get_db, get_http_client, get_app_state, require_editor
from app.config import settings
from app.services.database import get_dataset_metadata, delete_dataset,get_dataset_owner
from app.services.metabaseClient import get_session_token, delete_dashboard, delete_card, get_dashboard_card_ids

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

@router.delete("/datasets/{dataset_id}")
async def delete_dataset_by_id(dataset_id: str,
                               db=Depends(get_db),
                               http_client=Depends(get_http_client),
                               app_state=Depends(get_app_state),
                               current_user=Depends(require_editor)):
    metadata = await get_dataset_metadata(dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete Metabase dashboard if one was created    
    dashboard_id = metadata.get("metabase_dashboard_id")
    if dashboard_id:
        try:
            token = await get_session_token(http_client, app_state)
            card_ids = await get_dashboard_card_ids(token, http_client, dashboard_id)
            await delete_dashboard(token, dashboard_id)
            for card_id in card_ids:
                await delete_card(token, http_client, card_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Metabase cleanup failed: {str(e)}")

    # Delete uploaded CSV file
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    for f in matches:
        f.unlink(missing_ok=True)

    # Delete Postgres table and all metadata rows
    await delete_dataset(dataset_id, metadata["table_name"])

    return {"deleted": dataset_id}