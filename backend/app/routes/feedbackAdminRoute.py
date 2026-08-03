from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.dependencies import get_db, get_current_user, require_admin
from app.services.database import create_feedback, get_admin_stats, get_admin_feedback
from typing import Literal
router = APIRouter()


class FeedbackRequest(BaseModel):
    type: Literal["idea", "bug", "other"]
    message: str | None = None
    dataset_id: str | None = None


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