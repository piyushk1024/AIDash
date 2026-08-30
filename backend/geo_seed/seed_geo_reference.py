import asyncio
import csv
import logging
import unicodedata
from collections import defaultdict
from pathlib import Path

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

DATABASE_URL = settings.DATABASE_URL_LOCAL or settings.DATABASE_URL

DATA_DIR = Path(__file__).parent / "data"
CITY_FILES = ["IndianCities.csv", "US_Cities.csv"]

INSERT_SQL = """
    INSERT INTO geo_reference
        (granularity, name, display_name, state, country, lat, lon, aliases)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (granularity, country, name) DO NOTHING
"""

def to_ascii(text):
    if not text:
        return text
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip()

def parse_aliases(raw):
    if not raw:
        return None
    return [a.strip().lower() for a in raw.split("|") if a.strip()]

def load_city_rows(filepath):
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = to_ascii(row["city_ascii"])
            state = to_ascii(row["admin_name"]) or None
            country = row["iso2"].strip().upper()
            population = int(row["population"]) if row.get("population") else 0
            rows.append({
                "name": name,
                "state": state,
                "country": country,
                "lat": float(row["lat"]),
                "lon": float(row["lng"]),
                "population": population,
            })
    return rows

def derive_state_rows(city_rows):
    # group by (country, state), pick the highest-population city as the state's point
    groups = defaultdict(list)
    for r in city_rows:
        if r["state"]:
            groups[(r["country"], r["state"])].append(r)

    state_rows = []
    for (country, state), cities in groups.items():
        top_city = max(cities, key=lambda c: c["population"])
        state_rows.append((
            "state",
            state.lower(),
            state,
            None,
            country,
            top_city["lat"],
            top_city["lon"],
            None,
        ))
    return state_rows

def city_rows_to_insert_tuples(city_rows):
    return [
        ("city", r["name"].lower(), r["name"], r["state"], r["country"], r["lat"], r["lon"], None)
        for r in city_rows
    ]

async def seed():
    conn = await asyncpg.connect(DATABASE_URL)
    all_city_rows = []

    try:
        for fname in CITY_FILES:
            rows = load_city_rows(DATA_DIR / fname)
            all_city_rows.extend(rows)
            logger.info(f"{fname}: {len(rows)} city rows loaded")

        city_tuples = city_rows_to_insert_tuples(all_city_rows)
        await conn.executemany(INSERT_SQL, city_tuples)
        logger.info(f"Inserted {len(city_tuples)} city rows")

        state_tuples = derive_state_rows(all_city_rows)
        await conn.executemany(INSERT_SQL, state_tuples)
        logger.info(f"Inserted {len(state_tuples)} state rows (derived, highest-population city as point)")

        count = await conn.fetchval("SELECT count(*) FROM geo_reference")
        logger.info(f"Seed complete. {count} total rows in geo_reference.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())