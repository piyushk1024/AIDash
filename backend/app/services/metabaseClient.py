import requests
from app.config import settings

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


def create_card(session_token: str, chart: dict) -> dict:
    
    query = {
        "database": DATABASE_ID,
        "type": "query",
        "query": {
            "source-table": TABLE_ID,
            "aggregation": [["sum", ["field", chart["y_axis"], {"base-type": "type/Integer"}]]],
            "breakout": [["field", chart["x_axis"], {"base-type": "type/Text"}]]
        }
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