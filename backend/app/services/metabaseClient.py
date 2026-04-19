import requests
from app.config import settings
import time

METABASE_URL = settings.METABASE_URL

def get_database_id(session_token: str) -> int:
    response = requests.get(
        f"{METABASE_URL}/api/database",
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()
    databases = response.json().get("data", [])
    match = next((db for db in databases if db["name"] == settings.METABASE_DB_NAME), None)
    if not match:
        raise ValueError(f"Database '{settings.METABASE_DB_NAME}' not found in Metabase")
    return match["id"]

def get_session_token() -> str:
    response = requests.post(
        f"{METABASE_URL}/api/session",
        json={
            "username": settings.METABASE_USERNAME,
            "password": settings.METABASE_PASSWORD
        }
    )
    response.raise_for_status()
    return response.json()["id"]


def create_card(session_token: str, chart: dict, table_id: int, field_map: dict, database_id:int,) -> dict:
    
    x_col = chart.get("x_axis")
    y_col = chart.get("y_axis")
    aggregation_type = chart.get("aggregation", "count")

    if aggregation_type == "count":
        aggregation = [["count"]]
    elif aggregation_type in ("sum", "avg"):
        if not y_col or y_col not in field_map:
            raise ValueError(f"y_axis '{y_col}' not found in field_map for {aggregation_type} aggregation")
        y_field = field_map[y_col]
        aggregation = [[aggregation_type, ["field", y_field["id"], {"base-type": y_field["base_type"]}]]]
    else:
        raise ValueError(f"Unsupported aggregation type: {aggregation_type}")

    query_clause = {
        "source-table": table_id,
        "aggregation": aggregation,
    }

    if x_col:
        if x_col not in field_map:
            raise ValueError(f"x_axis '{x_col}' not found in field_map")
        x_field = field_map[x_col]
        query_clause["breakout"] = [["field", x_field["id"], {"base-type": x_field["base_type"]}]]

    if chart.get("filters"):
        filter_col = chart["filters"][0]["column"]
        filter_val = chart["filters"][0]["value"]
        if filter_col not in field_map:
            raise ValueError(f"filter column '{filter_col}' not found in field_map")
        f_field = field_map[filter_col]
        query_clause["filter"] = [
            "=",
            ["field", f_field["id"], {"base-type": f_field["base_type"]}],
            filter_val
        ]
        

    query = {
        "database": database_id,
        "type": "query",
        "query": query_clause
    }

    payload = {
        "name": chart["chart_title"],
        "display": chart["chart_type"],
        "dataset_query": query,
        "visualization_settings": {}
    }

    response = requests.post(
        f"{METABASE_URL}/api/card",
        json=payload,
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()
    return response.json()


def create_dashboard(session_token: str, title: str) -> int:
    response = requests.post(
        f"{METABASE_URL}/api/dashboard",
        json={"name": title},
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()
    return response.json()["id"]

def add_card_to_dashboard(
    session_token: str, dashboard_id: int, card_id: int, position: int
) -> None:
    # First get current cards on dashboard
    get_response = requests.get(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        headers={"X-Metabase-Session": session_token}
    )
    get_response.raise_for_status()
    existing_cards = get_response.json().get("dashcards", [])

    new_card = {
        "id": -1,
        "card_id": card_id,
        "row": (position // 2) * 4,
        "col": (position % 2) * 12,
        "size_x": 12,
        "size_y": 4,
        "parameter_mappings": [],
        "visualization_settings": {}
    }

    response = requests.put(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        json={"dashcards": existing_cards + [new_card]},
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()

def trigger_metabase_sync(session_token: str, database_id: int) -> None:
    response = requests.post(
        f"{METABASE_URL}/api/database/{database_id}/sync_schema",
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()

def fetch_field_map_for_table(session_token: str, table_name: str,database_id: int, timeout: int = 30) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = requests.get(
            f"{METABASE_URL}/api/database/{database_id}/metadata",
            headers={"X-Metabase-Session": session_token}
        )
        response.raise_for_status()
        tables = response.json().get("tables", [])

        matched_table = next(
            (t for t in tables if t["name"].lower() == table_name.lower()), None
        )
        if matched_table:
            table_id = matched_table["id"]
            field_map = {}
            for field in matched_table.get("fields", []):
                field_map[field["name"]] = {
                    "id": field["id"],
                    "base_type": field["base_type"]
                }
            if field_map:
                return {"table_id": table_id, "field_map": field_map}

        time.sleep(2)

    raise TimeoutError(f"Metabase sync timed out after {timeout}s — table '{table_name}' not found")

def get_dashboard_card_ids(session_token: str, dashboard_id: int) -> list[int]:
    response = requests.get(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()
    dashcards = response.json().get("dashcards", [])
    return [dc["card_id"] for dc in dashcards]

def delete_card(session_token: str, card_id: int) -> None:
    response = requests.delete(
        f"{METABASE_URL}/api/card/{card_id}",
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()

def delete_dashboard(session_token: str, dashboard_id: int) -> None:
    response = requests.delete(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}",
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()

def create_public_link(session_token: str, dashboard_id: int) -> str:
    response = requests.post(
        f"{METABASE_URL}/api/dashboard/{dashboard_id}/public_link",
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()
    uuid = response.json()["uuid"]
    return f"{METABASE_URL}/public/dashboard/{uuid}"