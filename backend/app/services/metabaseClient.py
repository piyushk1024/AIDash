import requests
from app.config import settings
import time

METABASE_URL = settings.METABASE_URL
DATABASE_ID = 2
TABLE_ID = 11


FIELD_MAP = {
    "date": {"id": 93, "base_type": "type/Date"},
    "week_of_year": {"id": 94, "base_type": "type/Integer"},
    "day_of_week": {"id": 95, "base_type": "type/Text"},
    "is_weekend": {"id": 96, "base_type": "type/Boolean"},
    "holiday_flag": {"id": 97, "base_type": "type/Boolean"},
    "weather_tag": {"id": 98, "base_type": "type/Text"},
    "city": {"id": 99, "base_type": "type/Text"},
    "zone": {"id": 100, "base_type": "type/Text"},
    "mall_name": {"id": 101, "base_type": "type/Text"},
    "promo_event_flag": {"id": 102, "base_type": "type/Boolean"},
    "footfall": {"id": 103, "base_type": "type/Integer"},
    "occupancy_rate_pct": {"id": 104, "base_type": "type/Decimal"},
    "avg_dwell_mins": {"id": 105, "base_type": "type/Decimal"},
    "sales_amount_inr": {"id": 106, "base_type": "type/Decimal"},
    "parking_utilization_pct": {"id": 107, "base_type": "type/Decimal"},
    "maintenance_tickets": {"id": 108, "base_type": "type/Integer"},
    "energy_kwh": {"id": 109, "base_type": "type/Decimal"},
}

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


def create_card(session_token: str, chart: dict, table_id: int, field_map: dict) -> dict:
    
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

    query = {
        "database": DATABASE_ID,
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

def trigger_metabase_sync(session_token: str) -> None:
    response = requests.post(
        f"{METABASE_URL}/api/database/{DATABASE_ID}/sync_schema",
        headers={"X-Metabase-Session": session_token}
    )
    response.raise_for_status()

def fetch_field_map_for_table(session_token: str, table_name: str, timeout: int = 30) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = requests.get(
            f"{METABASE_URL}/api/database/{DATABASE_ID}/metadata",
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