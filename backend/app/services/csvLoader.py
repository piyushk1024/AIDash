import csv
import psycopg2
from pathlib import Path
from app.services.database import get_connection

TYPE_MAP = {
    "integer": "INTEGER",
    "float": "NUMERIC",
    "boolean": "BOOLEAN",
    "string": "TEXT",
    "unknown": "TEXT",
}

def sanitise_table_name(filename: str) -> str:
    name = Path(filename).stem
    name = name.lower()
    name = "".join(c if c.isalnum() else "_" for c in name)
    if name[0].isdigit():
        name = "t_" + name
    return name

def infer_type(values: list[str]) -> str:
    non_empty = [v for v in values if v not in (None, "", "null", "None")]
    if not non_empty:
        return "unknown"
    bool_set = {"true", "false", "0", "1"}
    if all(str(v).strip().lower() in bool_set for v in non_empty):
        return "boolean"
    try:
        for v in non_empty:
            int(str(v))
        return "integer"
    except Exception:
        pass
    try:
        for v in non_empty:
            float(str(v))
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
                    values.append(None if val in ("", "null", "None", "NA") else val)

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