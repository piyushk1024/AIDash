# app/services/csvLoader.py
import csv
from pathlib import Path
import asyncpg

NULL_VALUES = {"", "null", "none", "na", "n/a", "#n/a", "-", "?", "nan"}

TYPE_MAP = {
    "integer": "BIGINT",
    "float":   "NUMERIC",
    "boolean": "BOOLEAN",
    "string":  "TEXT",
    "unknown": "TEXT",
}

SUMMARY_KEYWORDS = {"total", "grand total", "subtotal", "sum", "overall", "aggregate"}


def sanitise_table_name(filename: str) -> str:
    name = Path(filename).stem
    name = name.lower()
    name = "".join(c if c.isalnum() else "_" for c in name)
    if name[0].isdigit():
        name = "t_" + name
    return name

def clean_value(v: str) -> str:
    return str(v).strip()

def is_null(v: str) -> bool:
    return clean_value(v).lower() in NULL_VALUES

def is_blank_row(row: dict) -> bool:
    return all(is_null(v) for v in row.values())

def is_summary_row(row: dict) -> bool:
    return any(clean_value(str(v)).lower() in SUMMARY_KEYWORDS for v in row.values())

def parse_number(v: str) -> str:
    return clean_value(v).replace(",", "").replace("%", "")

def infer_type(values: list[str]) -> str:
    non_empty = [v for v in values if not is_null(v)]
    if not non_empty:
        return "unknown"

    bool_set = {"true", "false", "0", "1"}
    if all(clean_value(v).lower() in bool_set for v in non_empty):
        return "boolean"

    try:
        for v in non_empty:
            int(parse_number(v))
        return "integer"
    except Exception:
        pass

    try:
        for v in non_empty:
            float(parse_number(v))
        return "float"
    except Exception:
        pass

    return "string"


async def load_csv_to_postgres(
    pool: asyncpg.Pool,
    file_path: Path,
    table_name: str,
) -> dict:
    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        columns = reader.fieldnames or []
        columns = [col if col.strip() else f"col_{i}" for i, col in enumerate(columns)]

    if not rows:
        raise ValueError("CSV is empty")

    rows = [r for r in rows if any(not is_null(v) for v in r.values())]
    rows = [r for r in rows if not is_blank_row(r) and not is_summary_row(r)]

    col_types = {col: infer_type([row.get(col, "") for row in rows]) for col in columns}

    col_definitions = ", ".join(
        f'"{col}" {TYPE_MAP[col_types[col]]}' for col in columns
    )

    # Build rows as tuples for executemany — one round trip for all inserts
    def coerce(val: str, col: str):
        if is_null(val):
            return None
        if col_types[col] == "integer":
            return int(parse_number(val))
        if col_types[col] == "float":
            return float(parse_number(val))
        if col_types[col] == "boolean":
            return clean_value(val).lower() in ("true", "1")
        return clean_value(val)

    tuples = [
        tuple(coerce(row.get(col, ""), col) for col in columns)
        for row in rows
    ]

    # placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
    # col_names    = ", ".join(f'"{c}"' for c in columns)

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            await conn.execute(f'CREATE TABLE "{table_name}" ({col_definitions})')
            await conn.copy_records_to_table(
                table_name,
                records=tuples,
                columns=columns,
            )

    return {
        "table_name": table_name,
        "row_count":  len(rows),
        "columns":    col_types,
    }