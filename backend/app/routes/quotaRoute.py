from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.services.quotaGuard import get_quota_status

router = APIRouter()


@router.get("/me/quota")
async def get_my_quota(current_user=Depends(get_current_user)):
    return await get_quota_status(current_user.user_id)