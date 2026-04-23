from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.database import get_cached_semantics, get_dataset_metadata
from app.services.profiler import profile_csv
from app.services.insightGenerator import generate_insights
from app.services.metabaseClient import get_session_token, execute_mbql_query
from app.config import settings

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR

class InsightRequest(BaseModel):
    prompt: str

@router.post("/datasets/{dataset_id}/insights")
async def get_insights(dataset_id: str, body: InsightRequest):

    semantics = get_cached_semantics(dataset_id)
    if not semantics:
        raise HTTPException(status_code=404, detail="No semantics found. Run inference first.")

    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset file not found.")
    profile = profile_csv(matches[0], dataset_id)

    metadata = get_dataset_metadata(dataset_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Dataset metadata not found.")

    table_name = metadata["table_name"]
    table_id = metadata["metabase_table_id"]
    field_map = metadata["field_map"]

    # Get database_id dynamically
    from app.services.metabaseClient import get_database_id
    session_token = get_session_token()
    database_id = get_database_id(session_token)

    def execute_mbql_fn(mbql: dict) -> dict:
        return execute_mbql_query(session_token, mbql)

    result = generate_insights(
        table_name=table_name,
        table_id=table_id,
        database_id=database_id,
        field_map=field_map,
        profile=profile,
        semantics=semantics,
        prompt=body.prompt,
        execute_mbql_fn=execute_mbql_fn
    )

    return result