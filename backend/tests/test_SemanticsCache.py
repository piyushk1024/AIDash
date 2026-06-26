import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY

from app.routes.semanticsRoute import infer_dataset_semantics
from app.schemas.semantics import InferSemanticsRequest

# ── Constants ────────────────────────────────────────────────────────────────

DATASET_ID = "test-dataset-id"
USER_ID    = "test-user-id"
HINT       = "retail mall operations"
NEW_HINT   = "cricket match statistics"

MODULE = "app.routes.semanticsRoute"

MOCK_PROFILE = {"columns": [{"name": "sales", "dtype": "float64"}]}

MOCK_SEMANTICS_JSON = {
    "dataset_id":   DATASET_ID,
    "business_hint": HINT,
    "dataset_grain": "row per transaction",
    "date_columns":  [],
    "dimensions":    [],
    "measures":      [],
    "flags":         [],
    "identifiers":   [],
    "unknown":       [],
    "notes":         [],
}

# Represents the shape returned by the updated get_cached_semantics
MOCK_CACHED_ROW = {
    "semantics_json": MOCK_SEMANTICS_JSON,
    "business_hint":  HINT,
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def make_mock_user():
    user = MagicMock()
    user.user_id = USER_ID
    return user


def make_mock_llm_result():
    """LLM result must support .model_dump() for persist_semantics."""
    result = MagicMock()
    result.model_dump.return_value = MOCK_SEMANTICS_JSON
    return result


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_miss_runs_inference():
    """No cached semantics → LLM is called, result is persisted, plan is NOT marked stale."""
    with (
        patch(f"{MODULE}.get_dataset_owner",    new_callable=AsyncMock) as mock_owner,
        patch(f"{MODULE}.get_cached_semantics", new_callable=AsyncMock) as mock_cached,
        patch(f"{MODULE}.get_cached_profile",   new_callable=AsyncMock) as mock_profile,
        patch(f"{MODULE}.infer_semantics_with_llm", new_callable=AsyncMock) as mock_llm,
        patch(f"{MODULE}.persist_semantics",    new_callable=AsyncMock) as mock_persist,
        patch(f"{MODULE}.mark_plan_stale",      new_callable=AsyncMock) as mock_stale,
    ):
        mock_owner.return_value   = USER_ID
        mock_cached.return_value  = None           # no cache
        mock_profile.return_value = MOCK_PROFILE
        mock_llm.return_value     = make_mock_llm_result()

        await infer_dataset_semantics(
            dataset_id=DATASET_ID,
            payload=InferSemanticsRequest(business_hint=HINT),
            force=False,
            db=MagicMock(),
            current_user=make_mock_user(),
        )

        mock_llm.assert_called_once()
        mock_persist.assert_called_once()
        mock_stale.assert_not_called()


@pytest.mark.asyncio
async def test_cache_hit_same_hint_returns_cached():
    """Cached row, same hint, no force → LLM skipped, nothing persisted, plan not touched."""
    with (
        patch(f"{MODULE}.get_dataset_owner",    new_callable=AsyncMock) as mock_owner,
        patch(f"{MODULE}.get_cached_semantics", new_callable=AsyncMock) as mock_cached,
        patch(f"{MODULE}.get_cached_profile",   new_callable=AsyncMock) as mock_profile,
        patch(f"{MODULE}.infer_semantics_with_llm", new_callable=AsyncMock) as mock_llm,
        patch(f"{MODULE}.persist_semantics",    new_callable=AsyncMock) as mock_persist,
        patch(f"{MODULE}.mark_plan_stale",      new_callable=AsyncMock) as mock_stale,
    ):
        mock_owner.return_value   = USER_ID
        mock_cached.return_value  = MOCK_CACHED_ROW  # cache hit, same hint
        mock_profile.return_value = MOCK_PROFILE

        await infer_dataset_semantics(
            dataset_id=DATASET_ID,
            payload=InferSemanticsRequest(business_hint=HINT),
            force=False,
            db=MagicMock(),
            current_user=make_mock_user(),
        )

        mock_llm.assert_not_called()
        mock_persist.assert_not_called()
        mock_stale.assert_not_called()


@pytest.mark.asyncio
async def test_force_flag_reruns_without_marking_stale():
    """Cached row, same hint, force=True → LLM reruns, persisted, plan NOT marked stale.
    Force means 'refresh the LLM result' not 'the hint changed' — downstream plan is still valid."""
    with (
        patch(f"{MODULE}.get_dataset_owner",    new_callable=AsyncMock) as mock_owner,
        patch(f"{MODULE}.get_cached_semantics", new_callable=AsyncMock) as mock_cached,
        patch(f"{MODULE}.get_cached_profile",   new_callable=AsyncMock) as mock_profile,
        patch(f"{MODULE}.infer_semantics_with_llm", new_callable=AsyncMock) as mock_llm,
        patch(f"{MODULE}.persist_semantics",    new_callable=AsyncMock) as mock_persist,
        patch(f"{MODULE}.mark_plan_stale",      new_callable=AsyncMock) as mock_stale,
    ):
        mock_owner.return_value   = USER_ID
        mock_cached.return_value  = MOCK_CACHED_ROW  # cache hit, same hint
        mock_profile.return_value = MOCK_PROFILE
        mock_llm.return_value     = make_mock_llm_result()

        await infer_dataset_semantics(
            dataset_id=DATASET_ID,
            payload=InferSemanticsRequest(business_hint=HINT),
            force=True,                              # force rerun
            db=MagicMock(),
            current_user=make_mock_user(),
        )

        mock_llm.assert_called_once()
        mock_persist.assert_called_once()
        mock_stale.assert_not_called()               # hint unchanged → plan stays valid


@pytest.mark.asyncio
async def test_hint_change_reruns_and_marks_plan_stale():
    """Cached row, different hint → LLM reruns, persisted, plan IS marked stale.
    Hint change means column classifications may shift — downstream plan is invalidated."""
    with (
        patch(f"{MODULE}.get_dataset_owner",    new_callable=AsyncMock) as mock_owner,
        patch(f"{MODULE}.get_cached_semantics", new_callable=AsyncMock) as mock_cached,
        patch(f"{MODULE}.get_cached_profile",   new_callable=AsyncMock) as mock_profile,
        patch(f"{MODULE}.infer_semantics_with_llm", new_callable=AsyncMock) as mock_llm,
        patch(f"{MODULE}.persist_semantics",    new_callable=AsyncMock) as mock_persist,
        patch(f"{MODULE}.mark_plan_stale",      new_callable=AsyncMock) as mock_stale,
    ):
        mock_owner.return_value   = USER_ID
        mock_cached.return_value  = MOCK_CACHED_ROW  # cached with old hint
        mock_profile.return_value = MOCK_PROFILE
        mock_llm.return_value     = make_mock_llm_result()

        await infer_dataset_semantics(
            dataset_id=DATASET_ID,
            payload=InferSemanticsRequest(business_hint=NEW_HINT),  # different hint
            force=False,
            db=MagicMock(),
            current_user=make_mock_user(),
        )

        mock_llm.assert_called_once()
        mock_persist.assert_called_once()
        mock_stale.assert_called_once_with(ANY, DATASET_ID)


@pytest.mark.asyncio
async def test_no_cache_with_force_does_not_mark_stale():
    """No cached row, force=True → hint_changed is False (nothing to compare against).
    LLM runs, persisted, plan NOT marked stale."""
    with (
        patch(f"{MODULE}.get_dataset_owner",    new_callable=AsyncMock) as mock_owner,
        patch(f"{MODULE}.get_cached_semantics", new_callable=AsyncMock) as mock_cached,
        patch(f"{MODULE}.get_cached_profile",   new_callable=AsyncMock) as mock_profile,
        patch(f"{MODULE}.infer_semantics_with_llm", new_callable=AsyncMock) as mock_llm,
        patch(f"{MODULE}.persist_semantics",    new_callable=AsyncMock) as mock_persist,
        patch(f"{MODULE}.mark_plan_stale",      new_callable=AsyncMock) as mock_stale,
    ):
        mock_owner.return_value   = USER_ID
        mock_cached.return_value  = None             # no cache
        mock_profile.return_value = MOCK_PROFILE
        mock_llm.return_value     = make_mock_llm_result()

        await infer_dataset_semantics(
            dataset_id=DATASET_ID,
            payload=InferSemanticsRequest(business_hint=HINT),
            force=True,
            db=MagicMock(),
            current_user=make_mock_user(),
        )

        mock_llm.assert_called_once()
        mock_persist.assert_called_once()
        mock_stale.assert_not_called()