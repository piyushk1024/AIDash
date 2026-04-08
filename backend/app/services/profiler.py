import csv
from pathlib import Path
import pandas as pd

def infer_basic_type(values: list[str]) -> str:
    
    non_empty = [v for v in values if v not in (None, "", "null", "NULL", "NA", "N/A", "na", "n/a")]
    # non_empty = [v for v in values if v not in (None, "", "null", "NULL")]
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

    # Load into pandas for statistical profiling
    df = pd.read_csv(file_path, encoding="utf-8-sig")

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = [c for c in df.columns if c not in numeric_cols]

    # Correlation matrix for numeric columns
    correlations = {}
    if len(numeric_cols) > 1:
        corr = df[numeric_cols].corr().round(2)
        for col in numeric_cols:
            correlations[col] = {
                other: (None if pd.isna(corr.loc[col, other]) else corr.loc[col, other])
                for other in numeric_cols
                if other != col
                }


    # Grouped stats: for each categorical col, compute numeric means per group
    grouped_stats = {}
    for cat_col in categorical_cols:
        if df[cat_col].nunique() <= 20 and numeric_cols:
            group = df.groupby(cat_col)[numeric_cols].mean().round(2)            
            group_dict = group.to_dict()
            # Replace NaN with None after conversion
            cleaned = {}
            for num_col, district_vals in group_dict.items():
                cleaned[num_col] = {
                    k: (None if pd.isna(v) else v)
                    for k, v in district_vals.items()
                }
            grouped_stats[cat_col] = cleaned


    profile_columns = []
    for col in columns:
        values = [row.get(col, "") for row in rows]
        non_null_values = [v for v in values if v not in (None, "")]
        distinct_values = list(dict.fromkeys(non_null_values))

        col_profile = {
            "column_name": col,
            "inferred_type": infer_basic_type(non_null_values[:50]),
            "sample_values": distinct_values[:5],
            "null_count": len(values) - len(non_null_values),
            "distinct_count": len(set(non_null_values)),
        }

        if col in numeric_cols:
            desc = df[col].describe().round(2).to_dict()
            col_profile["stats"] = {
                k: (None if pd.isna(v) else v)
                for k, v in {
                    "mean": desc.get("mean"),
                    "std": desc.get("std"),
                    "min": desc.get("min"),
                    "max": desc.get("max"),
                    "p25": desc.get("25%"),
                    "p50": desc.get("50%"),
                    "p75": desc.get("75%"),
                }.items()
}
            if col in correlations:
                col_profile["correlations"] = correlations[col]

        elif col in categorical_cols:
            col_profile["value_counts"] = (
                df[col].value_counts().head(10).to_dict()
            )

        profile_columns.append(col_profile)

    return {
        "dataset_id": dataset_id,
        "file_name": file_path.name,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": profile_columns,
        "grouped_stats": grouped_stats,
    }