from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.database import (
    get_cached_semantics,
    get_dataset_metadata,
    persist_insight,
    get_insights_for_dataset,
    delete_insight,
    get_dataset_owner,
    get_cached_profile
)

from app.services.insightGenerator import generate_insights
from app.services.queryExecutor import execute_raw_query
from app.dependencies import get_db, get_current_user

router = APIRouter()

class InsightRequest(BaseModel):
    prompt: str

@router.post("/datasets/{dataset_id}/insights")
async def post_insight(
    dataset_id: str,
    body: InsightRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    semantics = await get_cached_semantics(db, dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    table_name = metadata["table_name"]
    field_map = metadata["field_map"]

    profile = await get_cached_profile(db, dataset_id)

    async def execute_sql_fn(sql: str) -> dict:
        return await execute_raw_query(db, sql, table_name)

    result = await generate_insights(
        table_name=table_name,
        field_map=field_map,
        profile=profile,
        semantics=semantics,
        prompt=body.prompt,
        execute_sql_fn=execute_sql_fn,
    )

    insight_id = await persist_insight(db, dataset_id, body.prompt, result["insights"])

    return {
        "insight_id": insight_id,
        "prompt": body.prompt,
        "insights": result["insights"],
    }


@router.get("/datasets/{dataset_id}/insights")
async def get_insights(
    dataset_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"insights": await get_insights_for_dataset(db, dataset_id)}

@router.delete("/datasets/{dataset_id}/insights/{insight_id}")
async def delete_insight_entry(
    dataset_id: str,
    insight_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    await delete_insight(db, dataset_id, insight_id)
    return {"deleted": insight_id}