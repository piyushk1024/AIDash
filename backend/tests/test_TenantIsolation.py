import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.routes.dashboardRoute import generate_plan, build_dashboard
from app.routes.datasetsRoute import get_state, publish_dashboard, PublishRequest
from app.routes.insightsRoute import post_insight, get_insights, delete_insight_entry, InsightRequest
from app.routes.semanticsRoute import infer_dataset_semantics
from app.schemas.semantics import InferSemanticsRequest
from app.routes.nlDashboardRoute import add_nl_chart, edit_nl_chart, delete_nl_chart, NLChartRequest
from app.routes.agentRoute import run_agent_dashboard, get_agent_dashboard_report, AgentRequest, ReportRequest
from app.routes.profilerRoute import profile_csv_route
from app.routes.cleanupRoute import delete_dataset_by_id

# fake test variables

os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret")


# ── Constants ────────────────────────────────────────────────────────────────

DATASET_ID  = "test-dataset-id"
OWNER_ID    = "owner-user-id"
ATTACKER_ID = "attacker-user-id"

MOCK_SEMANTICS = {"dataset_grain": "row per transaction"}


def make_mock_attacker():
    user = MagicMock()
    user.user_id = ATTACKER_ID
    return user


# ── Helper: assert a call raises 403, not any other status ─────────────────

async def assert_403(coro):
    with pytest.raises(HTTPException) as exc_info:
        await coro
    assert exc_info.value.status_code == 403


# ── dashboardRoute ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_plan_blocks_non_owner():
    with patch("app.routes.dashboardRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(generate_plan(
            dataset_id=DATASET_ID, db=MagicMock(), current_user=make_mock_attacker(),
        ))


@pytest.mark.asyncio
async def test_build_dashboard_blocks_non_owner():
    with patch("app.routes.dashboardRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(build_dashboard(
            dataset_id=DATASET_ID, db=MagicMock(), current_user=make_mock_attacker(),
        ))


# ── datasetsRoute ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_state_blocks_non_owner():
    with (
        patch("app.routes.datasetsRoute.get_dataset_state", new_callable=AsyncMock) as mock_state,
        patch("app.routes.datasetsRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner,
    ):
        mock_state.return_value = {"metadata": {}}
        mock_owner.return_value = OWNER_ID
        await assert_403(get_state(
            dataset_id=DATASET_ID, db=MagicMock(), current_user=make_mock_attacker(),
        ))


@pytest.mark.asyncio
async def test_publish_dashboard_blocks_non_owner():
    with patch("app.routes.datasetsRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(publish_dashboard(
            dataset_id=DATASET_ID, body=PublishRequest(mode="pipeline"),
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


# ── insightsRoute ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_insight_blocks_non_owner():
    with (
        patch("app.routes.insightsRoute.get_cached_semantics", new_callable=AsyncMock) as mock_semantics,
        patch("app.routes.insightsRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner,
    ):
        mock_semantics.return_value = MOCK_SEMANTICS
        mock_owner.return_value = OWNER_ID
        await assert_403(post_insight(
            dataset_id=DATASET_ID, body=InsightRequest(prompt="anything"),
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


@pytest.mark.asyncio
async def test_get_insights_blocks_non_owner():
    with patch("app.routes.insightsRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(get_insights(
            dataset_id=DATASET_ID, db=MagicMock(), current_user=make_mock_attacker(),
        ))


@pytest.mark.asyncio
async def test_delete_insight_blocks_non_owner():
    with patch("app.routes.insightsRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(delete_insight_entry(
            dataset_id=DATASET_ID, insight_id="insight-1",
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


# ── semanticsRoute ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_infer_semantics_blocks_non_owner():
    with patch("app.routes.semanticsRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(infer_dataset_semantics(
            dataset_id=DATASET_ID, payload=InferSemanticsRequest(business_hint="anything"),
            force=False, db=MagicMock(), current_user=make_mock_attacker(),
        ))


# ── nlDashboardRoute (owner check lives in shared _get_common_deps) ────────

@pytest.mark.asyncio
async def test_add_nl_chart_blocks_non_owner():
    with (
        patch("app.routes.nlDashboardRoute.get_cached_semantics", new_callable=AsyncMock) as mock_semantics,
        patch("app.routes.nlDashboardRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner,
    ):
        mock_semantics.return_value = MOCK_SEMANTICS
        mock_owner.return_value = OWNER_ID
        await assert_403(add_nl_chart(
            dataset_id=DATASET_ID, body=NLChartRequest(prompt="anything"),
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


@pytest.mark.asyncio
async def test_edit_nl_chart_blocks_non_owner():
    with (
        patch("app.routes.nlDashboardRoute.get_cached_semantics", new_callable=AsyncMock) as mock_semantics,
        patch("app.routes.nlDashboardRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner,
    ):
        mock_semantics.return_value = MOCK_SEMANTICS
        mock_owner.return_value = OWNER_ID
        await assert_403(edit_nl_chart(
            dataset_id=DATASET_ID, card_id="card-1", body=NLChartRequest(prompt="anything"),
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


@pytest.mark.asyncio
async def test_delete_nl_chart_blocks_non_owner():
    with (
        patch("app.routes.nlDashboardRoute.get_cached_semantics", new_callable=AsyncMock) as mock_semantics,
        patch("app.routes.nlDashboardRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner,
    ):
        mock_semantics.return_value = MOCK_SEMANTICS
        mock_owner.return_value = OWNER_ID
        await assert_403(delete_nl_chart(
            dataset_id=DATASET_ID, card_id="card-1", mode="pipeline",
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


# ── agentRoute (owner check lives in shared _setup_agent_run) ──────────────

@pytest.mark.asyncio
async def test_run_agent_dashboard_blocks_non_owner():
    with (
        patch("app.routes.agentRoute.get_cached_semantics", new_callable=AsyncMock) as mock_semantics,
        patch("app.routes.agentRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner,
    ):
        mock_semantics.return_value = MOCK_SEMANTICS
        mock_owner.return_value = OWNER_ID
        await assert_403(run_agent_dashboard(
            dataset_id=DATASET_ID, body=AgentRequest(goal="anything"),
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


@pytest.mark.asyncio
async def test_get_agent_report_blocks_non_owner():
    with patch("app.routes.agentRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(get_agent_dashboard_report(
            dataset_id=DATASET_ID, body=ReportRequest(charts=[]),
            db=MagicMock(), current_user=make_mock_attacker(),
        ))


# ── profilerRoute ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_profile_csv_blocks_non_owner():
    with patch("app.routes.profilerRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = OWNER_ID
        await assert_403(profile_csv_route(
            dataset_id=DATASET_ID, db=MagicMock(), current_user=make_mock_attacker(),
        ))


# ── cleanupRoute ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_dataset_blocks_non_owner():
    with (
        patch("app.routes.cleanupRoute.get_dataset_metadata", new_callable=AsyncMock) as mock_meta,
        patch("app.routes.cleanupRoute.get_dataset_owner", new_callable=AsyncMock) as mock_owner,
    ):
        mock_meta.return_value = {"table_name": "irrelevant"}
        mock_owner.return_value = OWNER_ID
        await assert_403(delete_dataset_by_id(
            dataset_id=DATASET_ID, db=MagicMock(), current_user=make_mock_attacker(),
        ))