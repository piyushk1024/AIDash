from pathlib import Path
import csv

from fastapi import APIRouter, HTTPException

router = APIRouter()

UPLOAD_DIR = Path("app/uploads")


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


@router.get("/profile-csv/{dataset_id}")
def profile_csv(dataset_id: str):
    matches = list(UPLOAD_DIR.glob(f"{dataset_id}_*.csv"))
    if not matches:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = matches[0]

    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty")

    columns = reader.fieldnames or []
    profile = []

    for col in columns:
        values = [row.get(col, "") for row in rows]
        non_empty = [v for v in values if v not in (None, "", "null", "None")]
        sample_values = non_empty[:5]
        distinct_count = len(set(non_empty))
        null_count = len(values) - len(non_empty)
        inferred_type = infer_type(values)

        profile.append({
            "column_name": col,
            "inferred_type": inferred_type,
            "sample_values": sample_values,
            "null_count": null_count,
            "distinct_count": distinct_count,
        })

    candidate_date_columns = [
        p["column_name"] for p in profile
        if "date" in p["column_name"].lower()
    ]
    candidate_numeric_columns = [
        p["column_name"] for p in profile
        if p["inferred_type"] in ("integer", "float")
    ]
    candidate_categorical_columns = [
        p["column_name"] for p in profile
        if p["inferred_type"] == "string"
    ]

    return {
        "dataset_id": dataset_id,
        "file_name": file_path.name,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": profile,
        "candidate_date_columns": candidate_date_columns,
        "candidate_numeric_columns": candidate_numeric_columns,
        "candidate_categorical_columns": candidate_categorical_columns,
    }