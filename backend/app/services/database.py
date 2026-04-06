import json
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import settings

def get_connection():
    return psycopg2.connect(settings.DATABASE_URL)

def get_cached_semantics(dataset_id: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT semantics_json FROM dataset_semantics WHERE dataset_id = %s",
                (dataset_id,)
            )
            row = cur.fetchone()
            return row["semantics_json"] if row else None

def persist_semantics(dataset_id: str, business_hint: str | None, semantics: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dataset_semantics (dataset_id, business_hint, semantics_json)
                VALUES (%s, %s, %s)
                ON CONFLICT (dataset_id) DO UPDATE
                SET semantics_json = EXCLUDED.semantics_json,
                    business_hint = EXCLUDED.business_hint,
                    inferred_at = NOW()
                """,
                (dataset_id, business_hint, json.dumps(semantics))
            )
        conn.commit()

def get_cached_dashboard_plan(dataset_id: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT plan_json FROM dashboard_plans WHERE dataset_id = %s ORDER BY created_at DESC LIMIT 1",
                (dataset_id,)
            )
            row = cur.fetchone()
            return row["plan_json"] if row else None

def persist_dashboard_plan(dataset_id: str, plan: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dashboard_plans (dataset_id, plan_json)
                VALUES (%s, %s)
                """,
                (dataset_id, json.dumps(plan))
            )
        conn.commit()

def persist_dataset_metadata(dataset_id: str, table_name: str, metabase_table_id: int, field_map: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dataset_metadata (dataset_id, table_name, metabase_table_id, field_map)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dataset_id) DO UPDATE
                SET table_name = EXCLUDED.table_name,
                    metabase_table_id = EXCLUDED.metabase_table_id,
                    field_map = EXCLUDED.field_map,
                    updated_at = NOW()
                """,
                (dataset_id, table_name, metabase_table_id, json.dumps(field_map))
            )
        conn.commit()

def get_dataset_metadata(dataset_id: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT table_name, metabase_table_id, field_map FROM dataset_metadata WHERE dataset_id = %s",
                (dataset_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
