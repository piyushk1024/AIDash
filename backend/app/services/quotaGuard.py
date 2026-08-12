"""LLM daily call quota — fairness guard on the shared Gemini free-tier pool.

Every LLM call funnels through llm.py's generate()/generate_with_tools(),
so the check lives there. user_id reaches this module via a contextvar set
once in dependencies.get_current_user, avoiding param-threading through
every caller (agentOrchestrator, dashboardPlanner, insightGenerator,
llmClient, nlChartBuilder, selfHealer).

The DB pool is a single long-lived object, not per-request, so it's held
as a module-level reference set once at startup via init_quota_guard() —
same lifecycle as app.state.db_pool, just mirrored here so llm.py doesn't
need pool param-threading either.

Reset is timezone-aligned with Gemini's actual RPD reset (midnight Pacific
Time), not server-local midnight — otherwise a user could hit our quota
hours before or after their real Google quota resets. daily_llm_usage
holds one row per user; usage_date is the last date that row was touched,
not a key — a stale usage_date (not today, PT) is read as zero usage and
overwritten fresh rather than accumulated.
"""
import asyncpg

from app.config import settings
from contextvars import ContextVar

_pool: asyncpg.Pool | None = None
_current_user_id: ContextVar[str] = ContextVar("current_user_id")
_last_quota_status: ContextVar[dict | None] = ContextVar("last_quota_status", default=None)
_TODAY_PT = "(NOW() AT TIME ZONE 'America/Los_Angeles')::date"


class QuotaExceededError(Exception):
    """Raised when a user has hit their daily LLM call quota."""
    def __init__(self, user_id: str, limit: int):
        self.user_id = user_id
        self.limit = limit
        super().__init__(f"User '{user_id}' hit daily LLM call limit ({limit}).")

async def get_current_user_quota() -> dict:
    return await get_quota_status(_current_user_id.get())

def init_quota_guard(pool: asyncpg.Pool) -> None:
    global _pool
    _pool = pool


def set_current_user_id(user_id: str) -> None:
    _current_user_id.set(user_id)

async def get_quota_status(user_id: str) -> dict:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT daily_call_limit, is_privileged FROM users WHERE user_id = $1", user_id
        )

        if row and row["is_privileged"]:
            return {"limit": None, "calls_used": None, "remaining": None, "unlimited": True}

        limit = row["daily_call_limit"] if row else None

        if limit == -1:
            return {"limit": None, "calls_used": None, "remaining": None, "unlimited": True}

        if limit is None:
            limit = settings.DAILY_CALL_LIMIT

        usage_row = await conn.fetchrow(
            f"""
            SELECT calls_used
            FROM daily_llm_usage
            WHERE user_id = $1 AND usage_date = {_TODAY_PT}
            """,
            user_id,
        )
        calls_used = usage_row["calls_used"] if usage_row else 0

        return {
            "limit": limit,
            "calls_used": calls_used,
            "remaining": max(limit - calls_used, 0),
            "unlimited": False,
        }

async def reserve_quota_slot() -> None:
    """Atomically check-and-increment usage. Raises QuotaExceededError if
    the user is already at their limit. SELECT ... FOR UPDATE on the
    user's row serializes concurrent requests from the same user, closing
    the check-then-increment race that existed when check and increment
    were separate round trips spanning the LLM call.

    Must be paired with refund_quota_slot() on any failure path after
    this succeeds, so failed LLM calls don't count against quota (same
    behavior as before: only successful calls consume quota).
    """
    user_id = _current_user_id.get()
    async with _pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT daily_call_limit, is_privileged FROM users WHERE user_id = $1 FOR UPDATE",
                user_id,
            )

            if row and row["is_privileged"]:
                limit = None
            else:
                limit = row["daily_call_limit"] if row else None
                if limit == -1:
                    limit = None
                elif limit is None:
                    limit = settings.DAILY_CALL_LIMIT

            if limit is not None:
                usage_row = await conn.fetchrow(
                    f"""
                    SELECT calls_used
                    FROM daily_llm_usage
                    WHERE user_id = $1 AND usage_date = {_TODAY_PT}
                    """,
                    user_id,
                )
                calls_used = usage_row["calls_used"] if usage_row else 0
                if calls_used >= limit:
                    raise QuotaExceededError(user_id, limit)

            await conn.execute(
                f"""
                INSERT INTO daily_llm_usage (user_id, usage_date, calls_used)
                VALUES ($1, {_TODAY_PT}, 1)
                ON CONFLICT (user_id) DO UPDATE
                SET calls_used = CASE
                        WHEN daily_llm_usage.usage_date = {_TODAY_PT}
                            THEN daily_llm_usage.calls_used + 1
                        ELSE 1
                    END,
                    usage_date = {_TODAY_PT}
                """,
                user_id,
            )

    status = await get_quota_status(user_id)
    _last_quota_status.set(status)


async def refund_quota_slot() -> None:
    """Decrement usage by 1. Call on any failure path after a successful
    reserve_quota_slot(), so a failed LLM call doesn't count against the
    user's daily quota.
    """
    user_id = _current_user_id.get()
    async with _pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE daily_llm_usage
            SET calls_used = GREATEST(calls_used - 1, 0)
            WHERE user_id = $1 AND usage_date = {_TODAY_PT}
            """,
            user_id,
        )
    status = await get_quota_status(user_id)
    _last_quota_status.set(status)
    
def get_last_quota_status() -> dict | None:
    return _last_quota_status.get()

