import csv
import psycopg2
from pathlib import Path
from app.services.database import get_connection

NULL_VALUES = {"", "null", "none", "na", "n/a", "#n/a", "-", "?", "nan"}

TYPE_MAP = {
    "integer": "BIGINT",
    "float": "NUMERIC",
    "boolean": "BOOLEAN",
    "string": "TEXT",
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
    """Strip commas and % signs to handle Indian-formatted numbers and percentages."""
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

def load_csv_to_postgres(file_path: Path, table_name: str) -> dict:
    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        columns = reader.fieldnames or []

    if not rows:
        raise ValueError("CSV is empty")

    # Skip blank trailing rows and summary rows
    rows = [r for r in rows if any(not is_null(v) for v in r.values())]
    rows = [r for r in rows if not is_blank_row(r) and not is_summary_row(r)]

    col_types = {}
    for col in columns:
        values = [row.get(col, "") for row in rows]
        col_types[col] = infer_type(values)

    col_definitions = ", ".join(
        f'"{col}" {TYPE_MAP[col_types[col]]}' for col in columns
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            cur.execute(f'CREATE TABLE "{table_name}" ({col_definitions})')

            for row in rows:
                values = []
                for col in columns:
                    val = row.get(col, "")
                    if is_null(val):
                        values.append(None)
                    elif col_types[col] in ("integer", "float"):
                        values.append(parse_number(val))
                    else:
                        values.append(clean_value(val))

                placeholders = ", ".join(["%s"] * len(columns))
                col_names = ", ".join(f'"{c}"' for c in columns)
                cur.execute(
                    f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})',
                    values
                )
        conn.commit()

    return {
        "table_name": table_name,
        "row_count": len(rows),
        "columns": col_types,
    }