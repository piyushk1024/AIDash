import asyncio
import time
import httpx
import logging
from app.config import settings
from app.schemas.chartTypes import (
    NO_VIZ_SETTINGS_TYPES,
    DIMENSION_MEASURE_TYPES,
    MEASURE_PAIR_TYPES,
    SERIES_CAPABLE_TYPES,
    PASSTHROUGH_TYPES,
)

METABASE_URL = settings.METABASE_URL
METABASE_PUBLIC_URL = settings.METABASE_PUBLIC_URL

async def get_session_token(http_client: httpx.AsyncClient, app_state) -> str:
    now = time.monotonic()
    if app_state.metabase_token and now < app_state.metabase_token_expires:
        return app_state.metabase_token

    resp = await http_client.post(
        f"{METABASE_URL}/api/session",
        json={
            "username": settings.METABASE_USERNAME,
            "password": settings.METABASE_PASSWORD,
        },
    )
    resp.raise_for_status()
    app_state.metabase_token = resp.json()["id"]
    app_state.metabase_token_expires = now + 3600
    return app_state.metabase_token


async def get_database_id(session_token: str, http_client: httpx.AsyncClient) -> int:
    resp = await http_client.get(
        f"{METABASE_URL}/api/database",
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    databases = resp.json().get("data", [])
    match = next((db for db in databases if db["name"] == settings.METABASE_DB_NAME), None)
    if not match:
        raise ValueError(f"Database '{settings.METABASE_DB_NAME}' not found in Metabase")
    return match["id"]


def _build_viz_settings(
    chart_type: str,
    x_alias: str | None,
    y_alias: str | None,
    series_alias: str | None,
    viz_params: dict | None,
) -> dict:
    """
    Tier A (scalar/bar/line/pie/row/scatter/table): Dasher builds
    visualization_settings itself from x_alias/y_alias/series_alias —
    the LLM never hand-writes Metabase viz JSON for these.

    Tier B (gauge/funnel/waterfall/pivot/map): the shape varies per
    instance (which bands, which stage order, which columns split
    where), so the LLM supplies viz_params directly. Raising here on a
    missing/empty dict routes the failure through the same two-stage
    self-healing cycle every other chart error already goes through —
    Dasher doesn't try to guess a shape on the LLM's behalf.
    """
    if chart_type in PASSTHROUGH_TYPES:
        if not isinstance(viz_params, dict) or not viz_params:
            raise ValueError(
                f"chart_type '{chart_type}' requires a non-empty viz_params dict."
            )
        return viz_params

    if chart_type in NO_VIZ_SETTINGS_TYPES:
        return {}

    if chart_type in DIMENSION_MEASURE_TYPES or chart_type in MEASURE_PAIR_TYPES:
        if not (x_alias and y_alias):
            return {}
        dimensions = [x_alias]
        if chart_type in SERIES_CAPABLE_TYPES and series_alias:
            dimensions.append(series_alias)
        return {
            "graph.dimensions": dimensions,
            "graph.metrics": [y_alias],
        }

    # Unrecognised chart_type — leave viz_settings empty rather than
    # guess a shape. Metabase renders with defaults; self-healer catches
    # anything that actually breaks.
    return {}


async def create_card(
    session_token: str,
    http_client: httpx.AsyncClient,
    chart_title: str,
    chart_type: str,
    sql: str,
    database_id: int,
    x_alias: str | None = None,
    y_alias: str | None = None,
    series_alias: str | None = None,
    viz_params: dict | None = None,
) -> dict:
    viz_settings = _build_viz_settings(chart_type, x_alias, y_alias, series_alias, viz_params)

    payload = {
        "name": chart_title,
        "display": chart_type,
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {"query": sql},
        },
        "visualization_settings": viz_settings,
    }

    resp = await http_client.post(
        f"{METABASE_URL}/api/card",
        json=payload,
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    return resp.json()

async def create_dashboard(
    session_token: str,
    http_client: httpx.AsyncClient,
    title: str,
) -> int:
    resp = await http_client.post(
        f"{METABASE_URL}/api/dashboard",
        json={"name": title},
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    return resp.json()["id"]


async def add_card_to_dashboard(
    session_token: str,
    http_client: httpx.AsyncClient,
    dashboard_id: int,
    card_id: int,
    position: int,
) -> None:
    get_resp = await http_client.get(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        headers={"X-Metabase-Session": session_token},
    )
    get_resp.raise_for_status()
    existing_cards = get_resp.json().get("dashcards", [])

    new_card = {
        "id": -1,
        "card_id": card_id,
        "row": (position // 2) * 4,
        "col": (position % 2) * 12,
        "size_x": 12,
        "size_y": 4,
        "parameter_mappings": [],
        "visualization_settings": {},
    }

    resp = await http_client.put(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        json={"dashcards": existing_cards + [new_card]},
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()


async def trigger_metabase_sync(
    session_token: str,
    http_client: httpx.AsyncClient,
    database_id: int,
) -> None:
    resp = await http_client.post(
        f"{METABASE_URL}/api/database/{database_id}/sync_schema",
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()


async def fetch_field_map_for_table(
    session_token: str,
    http_client: httpx.AsyncClient,
    table_name: str,
    database_id: int,
    timeout: int = settings.METABASE_SYNC_TIMEOUT,
) -> dict:
    interval = 0.5
    max_interval = 8.0
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        resp = await http_client.get(
            f"{METABASE_URL}/api/database/{database_id}/metadata",
            headers={"X-Metabase-Session": session_token},
        )
        resp.raise_for_status()
        tables = resp.json().get("tables", [])

        matched = next(
            (t for t in tables if t["name"].lower() == table_name.lower()), None
        )
        if matched:
            field_map = {
                field["name"]: {"id": field["id"], "base_type": field["base_type"]}
                for field in matched.get("fields", [])
            }
            if field_map:
                return {"table_id": matched["id"], "field_map": field_map}

        remaining = deadline - time.monotonic()
        sleep_for = min(interval, remaining)
        if sleep_for <= 0:
            break
        await asyncio.sleep(sleep_for)
        interval = min(interval * 2, max_interval)

    raise TimeoutError(
        f"Metabase sync timed out after {timeout}s — table '{table_name}' not found"
    )


async def get_dashboard_card_ids(
    session_token: str,
    http_client: httpx.AsyncClient,
    dashboard_id: int,
) -> list[int]:
    resp = await http_client.get(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    return [dc["card_id"] for dc in resp.json().get("dashcards", [])]

async def get_dashboard_cards(
    session_token: str,
    http_client: httpx.AsyncClient,
    dashboard_id: int,
) -> list[dict]:
    """Returns [{card_id, chart_title}] for diffing against a new plan."""
    resp = await http_client.get(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    return [
        {"card_id": dc["card_id"], "chart_title": dc["card"]["name"]}
        for dc in resp.json().get("dashcards", [])
        if dc.get("card")
    ]


async def delete_card(
    session_token: str,
    http_client: httpx.AsyncClient,
    card_id: int,
) -> None:
    resp = await http_client.delete(
        f"{METABASE_URL}/api/card/{card_id}",
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()


async def delete_dashboard(
    session_token: str,
    http_client: httpx.AsyncClient,
    dashboard_id: int,
) -> None:
    resp = await http_client.delete(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()


async def create_public_link(
    session_token: str,
    http_client: httpx.AsyncClient,
    dashboard_id: int,
) -> str:
    resp = await http_client.post(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}/public_link",
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    uuid = resp.json()["uuid"]
    return f"{METABASE_PUBLIC_URL}/public/dashboard/{uuid}"


async def execute_sql_query(
    session_token: str,
    http_client: httpx.AsyncClient,
    sql: str,
    database_id: int,
) -> dict:
    payload = {
        "database": database_id,
        "type": "native",
        "native": {"query": sql},
    }
    resp = await http_client.post(
        f"{METABASE_URL}/api/dataset",
        json=payload,
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    data = resp.json()
    cols = [col["name"] for col in data.get("data", {}).get("cols", [])]
    rows = data.get("data", {}).get("rows", [])
    return {
        "columns": cols,
        "rows": [dict(zip(cols, row)) for row in rows],
    }


async def validate_card_query(
    session_token: str,
    http_client: httpx.AsyncClient,
    card_id: int,
) -> str | None:
    resp = await http_client.post(
        f"{METABASE_URL}/api/card/{card_id}/query",
        headers={"X-Metabase-Session": session_token},
    )
    data = resp.json()
    return data.get("error") or data.get("data", {}).get("error")

async def update_card(
    session_token: str,
    http_client: httpx.AsyncClient,
    card_id: int,
    chart_title: str,
    chart_type: str,
    sql: str,
    database_id: int,
    x_alias: str | None = None,
    y_alias: str | None = None,
    series_alias: str | None = None,
    viz_params: dict | None = None,
) -> dict:
    viz_settings = _build_viz_settings(chart_type, x_alias, y_alias, series_alias, viz_params)
    payload = {
        "name": chart_title,
        "display": chart_type,
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {"query": sql},
        },
        "visualization_settings": viz_settings,
    }
    resp = await http_client.put(
        f"{METABASE_URL}/api/card/{card_id}",
        json=payload,
        headers={"X-Metabase-Session": session_token},
    )
    resp.raise_for_status()
    return resp.json()


async def sync_dashboard_cards(
    session_token: str,
    http_client: httpx.AsyncClient,
    dashboard_id: int,
    card_ids_in_order: list[int],
) -> None:
    dashcards = [
        {
            "id":-(i + 1),
            "card_id": card_id,
            "row": (i // 2) * 4,
            "col": (i % 2) * 12,
            "size_x": 12,
            "size_y": 4,
            "parameter_mappings": [],
            "visualization_settings": {},
        }
        for i, card_id in enumerate(card_ids_in_order)
    ]
    resp = await http_client.put(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        json={"dashcards": dashcards},
        headers={"X-Metabase-Session": session_token},
    )
    
    if resp.status_code >= 400:
      logger = logging.getLogger(__name__)
      logger.error("sync_dashboard_cards failed: %s", resp.text)

    resp.raise_for_status()