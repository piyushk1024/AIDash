from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.database import (
    get_cached_semantics,
    get_dataset_metadata,
    persist_insight,
    get_insights_for_dataset,
    delete_insight,
    get_dataset_owner
)
from app.services.profiler import profile_csv
from app.services.insightGenerator import generate_insights
from app.services.metabaseClient import (
    get_session_token,
    execute_sql_query,
    get_database_id,
)
from app.dependencies import get_db, get_http_client, get_app_state, get_current_user
from app.config import settings

router = APIRouter()
UPLOAD_DIR = settings.UPLOAD_DIR


class InsightRequest(BaseModel):
    prompt: str


@router.post("/datasets/{dataset_id}/insights")
async def post_insight(
    dataset_id: str,
    body: InsightRequest,
    db=Depends(get_db),
    http_client=Depends(get_http_client),
    app_state=Depends(get_app_state),
    current_user=Depends(get_current_user),
):
    semantics = await get_cached_semantics(db, dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")
    owner = await get_dataset_owner(db, dataset_id)
    if owner != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found.")
    profile = profile_csv(matches[0], dataset_id)

    metadata = await get_dataset_metadata(db, dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    table_name = metadata["table_name"]
    table_id = metadata["metabase_table_id"]
    field_map = metadata["field_map"]

    token = await get_session_token(http_client, app_state)
    database_id = await get_database_id(token, http_client)

    async def execute_sql_fn(sql: str) -> dict:
        return await execute_sql_query(token, http_client, sql, database_id)

    result = await generate_insights(
        table_name=table_name,
        table_id=table_id,
        database_id=database_id,
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
    return {"insights": await get_insights_for_dataset(db, dataset_id)}


@router.delete("/datasets/{dataset_id}/insights/{insight_id}")
async def delete_insight_entry(
    dataset_id: str,
    insight_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    await delete_insight(db, dataset_id, insight_id)
    return {"deleted": insight_id}