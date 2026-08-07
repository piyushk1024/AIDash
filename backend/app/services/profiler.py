import pandas as pd
from decimal import Decimal


def infer_basic_type(values: list[str]) -> str:

    non_empty = [v for v in values if v not in (None, "", "null", "NULL", "NA", "N/A", "na", "n/a")]
    if not non_empty:
        return "string"

    lowered = [str(v).strip().lower() for v in non_empty]

    if all(v in ("0", "1", "true", "false") for v in lowered):
        return "boolean"

    try:
        for v in non_empty:
            int(str(v))
        return "integer"
    except (ValueError, TypeError):
        pass

    try:
        for v in non_empty:
            float(str(v))
        return "float"
    except (ValueError, TypeError):
        pass

    return "string"


def _native(v):
    # Converts pandas/numpy scalar types (numpy.float64, numpy.int64, etc.)
    # to native Python types, and NaN to None. Anything from describe(),
    # value_counts(), or a correlation matrix comes back as a numpy scalar,
    # which plain json.dumps can't serialize — this is the single point
    # where that gets fixed, so every downstream consumer (JSONB storage,
    # LLM prompts, agent profile summaries) only ever sees plain types.
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "item"):
        return v.item()
    return v


async def profile_csv(pool, table_name: str, dataset_id: str) -> dict:
    async with pool.acquire() as conn:
        records = await conn.fetch(f'SELECT * FROM "{table_name}"')

    columns = list(records[0].keys()) if records else []
    rows = [dict(r) for r in records]

    if not rows:
        return {
            "dataset_id": dataset_id,
            "file_name": table_name,
            "row_count": 0,
            "column_count": 0,
            "columns": [],
        }

    df = pd.DataFrame(rows)

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = [c for c in df.columns if c not in numeric_cols]

    # Correlation matrix for numeric columns
    correlations = {}
    if len(numeric_cols) > 1:
        corr = df[numeric_cols].corr().round(2)
        for col in numeric_cols:
            correlations[col] = {
                other: _native(corr.loc[col, other])
                for other in numeric_cols
                if other != col
                }


    # Grouped stats: for each categorical col, compute numeric means per group
    grouped_stats = {}
    for cat_col in categorical_cols:
        if df[cat_col].nunique() <= 20 and numeric_cols:
            group = df.groupby(cat_col)[numeric_cols].mean().round(2)
            group_dict = group.to_dict()
            cleaned = {}
            for num_col, district_vals in group_dict.items():
                cleaned[num_col] = {
                    _native(k): _native(v)
                    for k, v in district_vals.items()
                }
            grouped_stats[cat_col] = cleaned

        # Coefficient of variation across group means — flags flat/low-signal
        # groupings before they reach chart planning.
            spread = {}
            for num_col in numeric_cols:
                means = group[num_col]
                mean_of_means = means.mean()
                if mean_of_means and mean_of_means != 0:
                    cv = _native((means.std() / abs(mean_of_means)))
                else:
                    cv = None
                spread[num_col] = round(cv, 4) if cv is not None else None
            grouped_stats[cat_col]["_spread_cv"] = spread


    profile_columns = []
    for col in columns:
        values = [row.get(col, "") for row in rows]
        non_null_values = [v for v in values if v not in (None, "")]
        distinct_values = list(dict.fromkeys(non_null_values))

        col_profile = {
            "column_name": col,
            "inferred_type": infer_basic_type(non_null_values[:50]),
            "sample_values": [_native(v) for v in distinct_values[:5]],
            "null_count": len(values) - len(non_null_values),
            "distinct_count": len(set(non_null_values)),
        }

        if col in numeric_cols:
            desc = df[col].describe().round(2).to_dict()
            col_profile["stats"] = {
                k: _native(v)
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
            col_profile["value_counts"] = {
                _native(k): _native(v)
                for k, v in df[col].value_counts().head(10).items()
            }

        profile_columns.append(col_profile)

    return {
        "dataset_id": dataset_id,
        "file_name": table_name,
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": profile_columns,
        "grouped_stats": grouped_stats,
    }