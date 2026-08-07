from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import get_db, require_editor

from app.services.database import get_dataset_metadata, delete_dataset, get_dataset_owner

router = APIRouter()


@router.delete("/datasets/{dataset_id}")
async def delete_dataset_by_id(dataset_id: str,
                               db=Depends(get_db),
                               current_user=Depends(require_editor)):
    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete Postgres table and all metadata rows — dashboard_plans rows
    # (which now hold all built chart results inline as JSONB) are deleted
    # here too, so this is the entire cleanup; nothing external to touch.
    await delete_dataset(db, dataset_id, metadata["table_name"])

    return {"deleted": dataset_id}