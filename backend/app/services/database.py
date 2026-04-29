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
                "SELECT table_name, metabase_table_id, field_map, metabase_dashboard_id,public_url FROM dataset_metadata WHERE dataset_id = %s",
                (dataset_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
        
def persist_metabase_dashboard_id(dataset_id: str, dashboard_id: int,public_url: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dataset_metadata
                SET metabase_dashboard_id = %s, public_url = %s
                WHERE dataset_id = %s
                """,
                (dashboard_id, public_url, dataset_id)
            )
        conn.commit()

def get_dashboard_cards(dataset_id: str) -> list[int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT plan_json FROM dashboard_plans WHERE dataset_id = %s ORDER BY created_at DESC LIMIT 1",
                (dataset_id,)
            )
            row = cur.fetchone()
            if not row:
                return []
            plan = row[0]
            return [chart["card_id"] for chart in plan.get("cards", [])] if "cards" in plan else []

def delete_dataset(dataset_id: str, table_name: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            cur.execute("DELETE FROM dashboard_plans WHERE dataset_id = %s", (dataset_id,))
            cur.execute("DELETE FROM dataset_semantics WHERE dataset_id = %s", (dataset_id,))
            cur.execute("DELETE FROM dataset_metadata WHERE dataset_id = %s", (dataset_id,))
            cur.execute("DELETE FROM dataset_insights WHERE dataset_id = %s", (dataset_id,))
        conn.commit()

def get_dataset_state(dataset_id: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Metadata (upload result equivalent)
            cur.execute(
                "SELECT table_name, metabase_table_id, field_map, metabase_dashboard_id,public_url FROM dataset_metadata WHERE dataset_id = %s",
                (dataset_id,)
            )
            metadata = cur.fetchone()

            # Semantics
            cur.execute(
                "SELECT semantics_json FROM dataset_semantics WHERE dataset_id = %s",
                (dataset_id,)
            )
            semantics_row = cur.fetchone()

            # Latest dashboard plan
            cur.execute(
                "SELECT plan_json FROM dashboard_plans WHERE dataset_id = %s ORDER BY created_at DESC LIMIT 1",
                (dataset_id,)
            )
            plan_row = cur.fetchone()

    if not metadata:
        return None

    return {
        "metadata": dict(metadata),
        "semantics": semantics_row["semantics_json"] if semantics_row else None,
        "plan": plan_row["plan_json"] if plan_row else None,
    }

def persist_insight(dataset_id: str, prompt: str, insights: list):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dataset_insights (dataset_id, prompt, insights_json)
                VALUES (%s, %s, %s)
                RETURNING insight_id
                """,
                (dataset_id, prompt, json.dumps(insights))
            )
            row = cur.fetchone()
        conn.commit()
        return str(row[0])

def get_insights_for_dataset(dataset_id: str) -> list:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT insight_id, prompt, insights_json, created_at
                FROM dataset_insights
                WHERE dataset_id = %s
                ORDER BY created_at DESC
                """,
                (dataset_id,)
            )
            rows = cur.fetchall()
    return [
        {
            "insight_id": str(row["insight_id"]),
            "prompt": row["prompt"],
            "insights": row["insights_json"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]
def delete_insight(dataset_id: str, insight_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM dataset_insights WHERE insight_id = %s AND dataset_id = %s",
                (insight_id, dataset_id)
            )
        conn.commit()