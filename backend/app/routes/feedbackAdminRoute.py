from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_db, get_current_user, require_admin
from app.services.database import create_feedback, get_admin_stats, get_admin_feedback, set_user_daily_call_limit, set_user_privilege
from typing import Literal
router = APIRouter()


class FeedbackRequest(BaseModel):
    type: Literal["idea", "bug", "other"]
    message: str | None = None
    dataset_id: str | None = None

class PrivilegeUpdateRequest(BaseModel):
    is_privileged: bool


@router.post("/feedback", status_code=201)
async def submit_feedback(
    body: FeedbackRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await create_feedback(db, current_user.user_id, body.dataset_id, body.type, body.message)

@router.get("/admin/stats")
async def admin_stats(
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await get_admin_stats(db)


@router.get("/admin/feedback")
async def admin_feedback(
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    return await get_admin_feedback(db)
class QuotaUpdateRequest(BaseModel):
    daily_call_limit: int | None  # null = reset to global default, -1 = unlimited


@router.patch("/admin/users/{username}/quota")
async def update_user_quota(
    username: str,
    body: QuotaUpdateRequest,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    updated = await set_user_daily_call_limit(db, username, body.daily_call_limit)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated

@router.patch("/admin/users/{username}/privilege")
async def update_user_privilege(
    username: str,
    body: PrivilegeUpdateRequest,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    updated = await set_user_privilege(db, username, body.is_privileged)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated