import csv
import asyncpg
import io
from pathlib import Path
from app.config import settings

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

def dedupe_columns(columns: list[str]) -> list[str]:
    seen = {}
    result = []
    for col in columns:
        if col not in seen:
            seen[col] = 0
            result.append(col)
        else:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
    return result

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
    content: bytes,
    table_name: str,
) -> dict:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("File is not valid UTF-8 text — not a readable CSV")

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        raise ValueError("Could not detect a valid delimiter — file may be malformed or not a CSV")

    try:
        raw_rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    except csv.Error as e:
        raise ValueError(f"Malformed CSV: {e}")

    if not raw_rows:
        raise ValueError("CSV is empty")

    header = raw_rows[0]
    data_rows = raw_rows[1:]

    if len(header) > settings.MAX_COLUMNS:
        raise ValueError(
            f"CSV has {len(header)} columns, exceeds limit of {settings.MAX_COLUMNS}"
        )

    header = [col if col.strip() else f"col_{i}" for i, col in enumerate(header)]
    # Dedupe before dict construction — DictReader would silently collapse
    # duplicate header names here otherwise.
    columns = dedupe_columns(header)

    rows = [dict(zip(columns, r)) for r in data_rows]

    if not rows:
        raise ValueError("CSV has no data rows")

    rows = [r for r in rows if any(not is_null(v) for v in r.values())]
    rows = [r for r in rows if not is_blank_row(r) and not is_summary_row(r)]

    if not rows:
        raise ValueError("CSV has no usable data rows after cleaning")

    if len(rows) > settings.MAX_ROWS:
        raise ValueError(
            f"CSV has {len(rows)} rows, exceeds limit of {settings.MAX_ROWS}"
        )

    col_types = {col: infer_type([row.get(col, "") for row in rows]) for col in columns}

    col_definitions = ", ".join(
        f'"{col}" {TYPE_MAP[col_types[col]]}' for col in columns
    )

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