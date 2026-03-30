import csv
from pathlib import Path


def infer_basic_type(values: list[str]) -> str:
    non_empty = [v for v in values if v not in (None, "", "null", "NULL")]
    if not non_empty:
        return "string"

    lowered = [str(v).strip().lower() for v in non_empty]

    if all(v in ("0", "1", "true", "false") for v in lowered):
        return "boolean"

    try:
        for v in non_empty:
            int(str(v))
        return "integer"
    except:
        pass

    try:
        for v in non_empty:
            float(str(v))
        return "float"
    except:
        pass

    return "string"


def profile_csv(file_path: Path, dataset_id: str) -> dict:
    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {
            "dataset_id": dataset_id,
            "file_name": file_path.name,
            "row_count": 0,
            "column_count": 0,
            "columns": [],
        }

    columns = reader.fieldnames or []
    profile_columns = []

    for col in columns:
        values = [row.get(col, "") for row in rows]
        non_null_values = [v for v in values if v not in (None, "")]
        distinct_values = list(dict.fromkeys(non_null_values))

        profile_columns.append(
            {
                "column_name": col,
                "inferred_type": infer_basic_type(non_null_values[:50]),
                "sample_values": distinct_values[:5],
                "null_count": len(values) - len(non_null_values),
                "distinct_count": len(set(non_null_values)),
            }
        )

    return {
        "dataset_id": dataset_id,
        "file_name": file_path.name,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": profile_columns,
    }
