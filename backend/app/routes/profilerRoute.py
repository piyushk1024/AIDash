from fastapi import APIRouter, HTTPException, Depends
from app.services.profiler import profile_csv
from app.dependencies import get_db, require_editor
from app.services.database import get_dataset_owner, get_cached_profile, persist_profile_json, get_dataset_metadata

router = APIRouter()

@router.get("/profile-csv/{dataset_id}")
async def profile_csv_route(
    dataset_id: str,
    db=Depends(get_db),
    current_user=Depends(require_editor),
):
    owner = await get_dataset_owner(db, dataset_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    cached = await get_cached_profile(db, dataset_id)
    if cached:
        return cached

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset not found")

    profile = await profile_csv(db, metadata["table_name"], dataset_id)
    await persist_profile_json(db, dataset_id, profile)
    return profile