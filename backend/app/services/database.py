# app/services/database.py
import json
import asyncpg
from app.config import settings


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Register JSON/JSONB codecs — asyncpg returns raw strings without this
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog',
    )
    await conn.set_type_codec(
        'json',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog',
    )


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=settings.DB_POOL_MIN,
        max_size=settings.DB_POOL_MAX,
        init=_init_connection,
    )


# ── Semantics ─────────────────────────────────────────────────

async def get_cached_semantics(pool: asyncpg.Pool, dataset_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT semantics_json, business_hint FROM dataset_semantics WHERE dataset_id = $1",
            dataset_id,
        )
        return {"semantics_json": row["semantics_json"], "business_hint": row["business_hint"]} if row else None


async def persist_semantics(
    pool: asyncpg.Pool,
    dataset_id: str,
    business_hint: str | None,
    semantics: dict,
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dataset_semantics (dataset_id, business_hint, semantics_json)
            VALUES ($1, $2, $3)
            ON CONFLICT (dataset_id) DO UPDATE
            SET semantics_json = EXCLUDED.semantics_json,
                business_hint  = EXCLUDED.business_hint,
                inferred_at    = NOW()
            """,
            dataset_id, business_hint, semantics,
        )


# ── Dashboard plans ───────────────────────────────────────────

async def get_cached_dashboard_plan(pool: asyncpg.Pool, dataset_id: str, mode: str | None = None):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT plan_json FROM dashboard_plans
            WHERE dataset_id = $1
              AND ($2::text IS NULL OR COALESCE(plan_json->>'mode', 'pipeline') = $2)
            ORDER BY created_at DESC LIMIT 1
            """,
            dataset_id, mode,
        )
        return row["plan_json"] if row else None


async def persist_dashboard_plan(pool: asyncpg.Pool, dataset_id: str, plan: dict):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO dashboard_plans (dataset_id, plan_json) VALUES ($1, $2)",
            dataset_id, plan,
        )


async def update_dashboard_plan(pool: asyncpg.Pool, dataset_id: str, plan: dict):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE dashboard_plans
            SET plan_json = $1
            WHERE plan_id = (
                SELECT plan_id FROM dashboard_plans
                WHERE dataset_id = $2
                ORDER BY created_at DESC
                LIMIT 1
            )
            """,
            plan, dataset_id,
        )


# ── Dataset metadata ──────────────────────────────────────────

async def persist_dataset_metadata(
    pool: asyncpg.Pool,
    dataset_id: str,
    table_name: str,
    metabase_table_id: int,
    field_map: dict,
    user_id: str,
    original_filename: str | None = None,
    file_checksum: str | None = None,
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO dataset_metadata
                (dataset_id, table_name, metabase_table_id, field_map, user_id,
                 original_filename, file_checksum)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (dataset_id) DO UPDATE
            SET table_name        = EXCLUDED.table_name,
                metabase_table_id = EXCLUDED.metabase_table_id,
                field_map         = EXCLUDED.field_map,
                user_id           = EXCLUDED.user_id,
                original_filename = EXCLUDED.original_filename,
                file_checksum     = EXCLUDED.file_checksum,
                updated_at        = NOW()
            """,
            dataset_id, table_name, metabase_table_id, field_map, user_id,
            original_filename, file_checksum,
        )

async def get_dataset_metadata(pool: asyncpg.Pool, dataset_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT table_name, metabase_table_id, field_map,
                   metabase_dashboard_id, public_url, user_id, published
            FROM dataset_metadata
            WHERE dataset_id = $1
            """,
            dataset_id,
        )
        return dict(row) if row else None

async def get_dataset_by_checksum(pool: asyncpg.Pool, checksum: str, user_id: str) -> str | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT dataset_id FROM dataset_metadata
            WHERE file_checksum = $1 AND user_id = $2
            """,
            checksum, user_id,
        )
        return row["dataset_id"] if row else None


async def persist_metabase_dashboard_id(
    pool: asyncpg.Pool,
    dataset_id: str,
    dashboard_id: int,
    public_url: str,
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE dataset_metadata
            SET metabase_dashboard_id = $1, public_url = $2
            WHERE dataset_id = $3
            """,
            dashboard_id, public_url, dataset_id,
        )


async def get_dataset_state(pool: asyncpg.Pool, dataset_id: str):
    # Single connection for all three queries — consistent read, one pool slot
    async with pool.acquire() as conn:
        metadata = await conn.fetchrow(
            """
            SELECT table_name, metabase_table_id, field_map,
                   metabase_dashboard_id, public_url, published
            FROM dataset_metadata
            WHERE dataset_id = $1
            """,
            dataset_id,
        )
        if not metadata:
            return None

        semantics_row = await conn.fetchrow(
            "SELECT semantics_json FROM dataset_semantics WHERE dataset_id = $1",
            dataset_id,
        )

        plan_row = await conn.fetchrow(
            """
            SELECT plan_json FROM dashboard_plans
            WHERE dataset_id = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            dataset_id,
        )

    return {
        "metadata": dict(metadata),
        "semantics": semantics_row["semantics_json"] if semantics_row else None,
        "plan":      plan_row["plan_json"] if plan_row else None,
    }


async def delete_dataset(pool: asyncpg.Pool, dataset_id: str, table_name: str):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            await conn.execute(
                "DELETE FROM dashboard_plans WHERE dataset_id = $1", dataset_id
            )
            await conn.execute(
                "DELETE FROM dataset_semantics WHERE dataset_id = $1", dataset_id
            )
            await conn.execute(
                "DELETE FROM dataset_metadata WHERE dataset_id = $1", dataset_id
            )
            await conn.execute(
                "DELETE FROM dataset_insights WHERE dataset_id = $1", dataset_id
            )


async def get_dashboard_cards(pool: asyncpg.Pool, dataset_id: str) -> list[int]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT plan_json FROM dashboard_plans
            WHERE dataset_id = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            dataset_id,
        )
        if not row:
            return []
        plan = row["plan_json"]
        return [c["card_id"] for c in plan.get("charts", []) if c.get("card_id")]


# ── Insights ──────────────────────────────────────────────────

async def persist_insight(
    pool: asyncpg.Pool,
    dataset_id: str,
    prompt: str,
    insights: list,
) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO dataset_insights (dataset_id, prompt, insights_json)
            VALUES ($1, $2, $3)
            RETURNING insight_id
            """,
            dataset_id, prompt, insights,
        )
    return str(row["insight_id"])


async def get_insights_for_dataset(pool: asyncpg.Pool, dataset_id: str) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT insight_id, prompt, insights_json, created_at
            FROM dataset_insights
            WHERE dataset_id = $1
            ORDER BY created_at DESC
            """,
            dataset_id,
        )
    return [
        {
            "insight_id": str(row["insight_id"]),
            "prompt":     row["prompt"],
            "insights":   row["insights_json"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


async def delete_insight(pool: asyncpg.Pool, dataset_id: str, insight_id: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM dataset_insights WHERE insight_id = $1 AND dataset_id = $2",
            insight_id, dataset_id,
        )

# ── auth stuff ──────────────────────────────────────────────────

async def create_user(pool: asyncpg.Pool, username: str, hashed_password: str, role: str) -> dict:
    row = await pool.fetchrow(
        """
        INSERT INTO users (username, hashed_password, role)
        VALUES ($1, $2, $3)
        RETURNING user_id, username, role
        """,
        username, hashed_password, role,
    )
    return dict(row)


async def get_user_by_username(pool: asyncpg.Pool, username: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT user_id, username, hashed_password, role FROM users WHERE username = $1",
        username,
    )
    return dict(row) if row else None

async def get_dataset_owner(pool: asyncpg.Pool, dataset_id: str) -> str | None:
    row = await pool.fetchrow(
        "SELECT user_id FROM dataset_metadata WHERE dataset_id = $1",
        dataset_id,
    )
    return row["user_id"] if row else None

# ── Publish ───────────────────────────────────────────────────

async def get_published_dashboard(pool: asyncpg.Pool, dataset_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT public_url, published
            FROM dataset_metadata
            WHERE dataset_id = $1
            """,
            dataset_id,
        )
        return dict(row) if row else None

async def set_published(pool: asyncpg.Pool, dataset_id: str, published: bool):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE dataset_metadata
            SET published = $1
            WHERE dataset_id = $2
            """,
            published, dataset_id,
        )

# ── Profile ───────────────────────────────────────────────────

async def get_cached_profile(pool: asyncpg.Pool, dataset_id: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT profile_json FROM dataset_metadata WHERE dataset_id = $1",
            dataset_id,
        )
        return row["profile_json"] if row else None

async def persist_profile_json(pool: asyncpg.Pool, dataset_id: str, profile: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE dataset_metadata SET profile_json = $1 WHERE dataset_id = $2",
            profile, dataset_id,
        )

async def mark_plan_stale(pool: asyncpg.Pool, dataset_id: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE dashboard_plans
            SET stale              = true,
                generation_counter = generation_counter + 1
            WHERE plan_id = (
                SELECT plan_id FROM dashboard_plans
                WHERE dataset_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            )
            """,
            dataset_id,
        )