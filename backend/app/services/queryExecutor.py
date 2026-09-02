import logging
from app.services.sqlGuard import validate_sql
from decimal import Decimal
import math
from app.schemas.chartTypes import ChartType, CHART_TYPE_REGISTRY, CHART_TYPE_VALUES
import json
from pathlib import Path

INDIA_BORDER_GEOJSON_PATH = Path(__file__).parent.parent / "static" / "geo" / "india-land-simplified.geojson"

def _load_india_border_geojson() -> dict:
    with open(INDIA_BORDER_GEOJSON_PATH) as f:
        return json.load(f)

logger = logging.getLogger(__name__)

TABLE_ROW_CAP = 15

def _cap_tabular_rows(rows: list[dict], chart: dict) -> list[dict]:
    """Table charts show individual records, not raw data dumps — cap to
    top N so cards/modal/exports never need to scroll or clip. Table
    charts have no y_alias, so this just takes the first N in query
    order. Falls back to a plain slice if y_alias is missing or
    non-numeric (avoids crashing the chart over a sort issue, capped
    output still beats an uncapped one)."""
    y_alias = chart.get("y_alias")
    if y_alias:
        try:
            rows = sorted(rows, key=lambda r: r.get(y_alias) or 0, reverse=True)
        except TypeError:
            pass
    return rows[:TABLE_ROW_CAP]

async def execute_chart_query(pool, chart: dict, table_name: str, profile: dict | None = None) -> dict:
    """
    Runs chart["sql"] through sqlGuard, executes it against the pool, and
    builds a Plotly spec (data + layout) from the result rows and chart_type.

    Returns {"rows": [...], "spec": {"data": [...], "layout": {...}}}.
    Raises ValueError on validation, execution, or shape errors — caller
    (cardBuilder) is expected to route these through the existing
    self-healing retry cycle.
    """
    chart_type_str = chart.get("chart_type")
    if chart_type_str in CHART_TYPE_VALUES and CHART_TYPE_REGISTRY[ChartType(chart_type_str)]["category"] == "correlation":
        return _build_correlation_spec(profile, chart)
    
    validate_sql(chart["sql"], table_name, context=chart.get("chart_title", ""))

    async with pool.acquire() as conn:
        records = await conn.fetch(chart["sql"])
    rows = [dict(r) for r in records]
    if chart.get("chart_type") == ChartType.TABLE.value:
        rows = _cap_tabular_rows(rows, chart)

    if chart_type_str in CHART_TYPE_VALUES and CHART_TYPE_REGISTRY[ChartType(chart_type_str)]["category"] == "map":
        return await _build_map_spec(pool, rows, chart)

    spec = _build_plotly_spec(rows, chart)
    return {"rows": rows, "spec": spec}

async def execute_raw_query(pool, sql: str, table_name: str) -> dict:
    """
    Executes raw SQL and returns rows only, no spec building. Used by
    inspect_data (agent) and insight generation. Runs sql through sqlGuard
    itself now (docstring previously assumed callers pre-validated —
    tracking down every raw-SQL call site to confirm that held was riskier
    than just validating here).
    """
    validate_sql(sql, table_name)
    async with pool.acquire() as conn:
        records = await conn.fetch(sql)
    return {"rows": [dict(r) for r in records]}

def _row_value(row: dict, alias: str, title: str):
    # Central point for reading a chart's declared alias out of an actual
    # result row. If the SQL's real output column name doesn't match what
    # the chart spec claims (alias/SQL drift), this raises a clear,
    # healer-actionable error instead of a bare KeyError.
    if alias not in row:
        raise ValueError(
            f"Column '{alias}' not found in query results ({title}). "
            f"Available columns: {list(row.keys())}"
        )
    return _sanitize_numeric(row[alias])

def _axis_title(chart: dict, label_key: str, alias_fallback: str | None) -> dict:
    # Prefers the LLM-authored x_label/y_label (human-readable, can carry
    # units) over the raw SQL alias. Falls back to the alias so no existing
    # plan breaks if the label field is absent — same backward-compat
    # pattern as every other optional chart field (series_alias, etc.).
    label = chart.get(label_key)
    return {"title": {"text": label or alias_fallback}}

def _sanitize_numeric(value, ndigits: int = 2):
    """Round floats/decimals for display; NaN/Infinity become None (avoids
    breaking JSON serialization downstream). Leaves ints, strings, dates,
    None untouched."""
    if isinstance(value, (float, Decimal)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, ndigits)
    return value

def _build_plotly_spec(rows: list[dict], chart: dict) -> dict:
    chart_type = ChartType(chart["chart_type"])
    title = chart.get("chart_title", "")
    layout = {"title": {"text": title}}

    if not rows:
        raise ValueError(f"Query returned no rows ({title})")

    record = CHART_TYPE_REGISTRY.get(chart_type)
    if record is None:
        raise ValueError(f"Unsupported chart type '{chart_type.value}' ({title})")
    category = record["category"]

    if category == "scalar":
        value = _sanitize_numeric(next(iter(rows[0].values())))
        return {"data": [{"type": "indicator", "mode": "number", "value": value}], "layout": layout}

    if category == "table":
        columns = list(rows[0].keys())
        trace = {
            "type": "table",
            "header": {"values": columns},
            "cells": {"values": [[_sanitize_numeric(row[col]) for row in rows] for col in columns]},
        }
        return {"data": [trace], "layout": layout}

    if category == "measure_pair":
        x_alias, y_alias = chart.get("x_alias"), chart.get("y_alias")
        _require_aliases(chart_type, x_alias, y_alias, title)
        series_alias = chart.get("series_alias") if record["series_capable"] else None

        if series_alias:
            data = _grouped_traces(chart_type, rows, x_alias, y_alias, series_alias, title)
        else:
            trace = {
                "type": "scatter",
                "mode": "markers",
                "x": [_row_value(r, x_alias, title) for r in rows],
                "y": [_row_value(r, y_alias, title) for r in rows],
            }
            data = [trace]
        layout["xaxis"] = _axis_title(chart, "x_label", x_alias)
        layout["yaxis"] = _axis_title(chart, "y_label", y_alias)
        return {"data": data, "layout": layout}

    if category == "dimension_measure":
        x_alias, y_alias = chart.get("x_alias"), chart.get("y_alias")
        _require_aliases(chart_type, x_alias, y_alias, title)
        series_alias = chart.get("series_alias") if record["series_capable"] else None

        if series_alias:
            data = _grouped_traces(chart_type, rows, x_alias, y_alias, series_alias, title)
            layout["barmode"] = "group"
        else:
            x = [_row_value(r, x_alias, title) for r in rows]
            y = [_row_value(r, y_alias, title) for r in rows]
            data = [_single_trace(chart_type, x, y)]

        if chart_type != ChartType.PIE:
            layout["xaxis"] = _axis_title(chart, "x_label", x_alias)
            layout["yaxis"] = _axis_title(chart, "y_label", y_alias)
        return {"data": data, "layout": layout}

    if category == "histogram":
        x_alias = chart.get("x_alias")
        if not x_alias:
            raise ValueError(f"x_alias required for chart type '{chart_type.value}' ({title})")
        series_alias = chart.get("series_alias") if record["series_capable"] else None

        if series_alias:
            data = _grouped_traces(chart_type, rows, x_alias, None, series_alias, title)
            for trace in data:
                trace["opacity"] = 0.65
            layout["barmode"] = "overlay"
        else:
            x = [_row_value(r, x_alias, title) for r in rows]
            data = [{"type": "histogram", "x": x}]
        layout["xaxis"] = _axis_title(chart, "x_label", x_alias)
        return {"data": data, "layout": layout}

    if category == "distribution":
        y_alias = chart.get("y_alias")
        if not y_alias:
            raise ValueError(f"y_alias required for chart type '{chart_type.value}' ({title})")
        trace = {"type": "box", "y": [_row_value(r, y_alias, title) for r in rows]}
        x_alias = chart.get("x_alias")
        if x_alias:
            trace["x"] = [_row_value(r, x_alias, title) for r in rows]
            layout["xaxis"] = _axis_title(chart, "x_label", x_alias)
        layout["yaxis"] = _axis_title(chart, "y_label", y_alias)
        return {"data": [trace], "layout": layout}

    if category == "sankey":
        trace = _build_sankey_trace(rows, chart, title)
        return {"data": [trace], "layout": layout}

    if category == "passthrough":
        trace = _passthrough_trace(chart_type, chart, rows, title)
        return {"data": [trace], "layout": layout}

    raise ValueError(f"Unsupported chart type '{chart_type.value}' ({title})")

def _require_aliases(chart_type: ChartType, x_alias, y_alias, title: str) -> None:
    if not x_alias or not y_alias:
        raise ValueError(f"x_alias/y_alias required for chart type '{chart_type.value}' ({title})")
    
def _single_trace(chart_type: ChartType, x: list, y: list) -> dict:
    if chart_type == ChartType.BAR:
        return {"type": "bar", "x": x, "y": y}
    if chart_type == ChartType.LINE:
        return {"type": "scatter", "mode": "lines+markers", "x": x, "y": y}
    if chart_type == ChartType.PIE:
        return {"type": "pie", "labels": x, "values": y}
    if chart_type == ChartType.SCATTER:
        return {"type": "scatter", "mode": "markers", "x": x, "y": y}
    if chart_type == ChartType.HISTOGRAM:
        return {"type": "histogram", "x": x}
    raise ValueError(f"No trace builder for chart type '{chart_type.value}'")

def _grouped_traces(chart_type: ChartType, rows: list[dict], x_alias: str, y_alias: str | None, series_alias: str, title: str) -> list[dict]:
    # One trace per distinct series value, preserving first-seen order.
    series_order: list = []
    grouped: dict = {}
    for r in rows:
        key = _row_value(r, series_alias, title)
        if key not in grouped:
            grouped[key] = []
            series_order.append(key)
        grouped[key].append(r)

    traces = []
    for key in series_order:
        group_rows = grouped[key]
        x = [_row_value(r, x_alias, title) for r in group_rows]
        y = [_row_value(r, y_alias, title) for r in group_rows] if y_alias else None
        trace = _single_trace(chart_type, x, y)
        trace["name"] = str(key)
        traces.append(trace)
    return traces

def _build_sankey_trace(rows: list[dict], chart: dict, title: str) -> dict:
    source_alias = chart.get("source_alias")
    target_alias = chart.get("target_alias")
    value_alias = chart.get("value_alias")
    if not source_alias or not target_alias or not value_alias:
        raise ValueError(
            f"source_alias/target_alias/value_alias required for sankey ({title})"
        )

    # Dedup labels across both columns, preserving first-seen order —
    # node.label needs one combined list, link.source/target are indices
    # into it, not the raw category strings.
    label_index: dict = {}
    labels: list = []
    for r in rows:
        for alias in (source_alias, target_alias):
            val = _row_value(r, alias, title)
            if val not in label_index:
                label_index[val] = len(labels)
                labels.append(val)

    source_idx = [label_index[_row_value(r, source_alias, title)] for r in rows]
    target_idx = [label_index[_row_value(r, target_alias, title)] for r in rows]
    values = [_row_value(r, value_alias, title) for r in rows]

    return {
        "type": "sankey",
        "node": {"label": labels},
        "link": {"source": source_idx, "target": target_idx, "value": values},
    }

def _build_correlation_spec(profile: dict | None, chart: dict) -> dict:
    title = chart.get("chart_title", "")
    if not profile:
        raise ValueError(f"Profile required for correlation heatmap ({title})")

    all_numeric_cols = [
        c["column_name"] for c in profile.get("columns", [])
        if "correlations" in c
    ]

    requested = chart.get("columns")
    if requested:
        # silently drop any requested name that isn't a valid numeric column
        numeric_cols = [c for c in requested if c in all_numeric_cols]
    else:
        numeric_cols = all_numeric_cols

    if len(numeric_cols) < 2:
        raise ValueError(f"Need at least 2 valid numeric columns for correlation heatmap ({title})")

    corr_lookup = {
        c["column_name"]: c["correlations"] for c in profile["columns"]
        if "correlations" in c
    }
    z = [
        [None if row_col == col_col else corr_lookup[row_col].get(col_col)
         for col_col in numeric_cols]
        for row_col in numeric_cols
    ]

    trace = {
        "type": "heatmap",
        "x": numeric_cols,
        "y": numeric_cols,
        "z": z,
        "colorscale": "Plasma",
    }
    spec = {"data": [trace], "layout": {"title": {"text": title}}}
    return {"rows": [], "spec": spec}

async def _build_map_spec(pool, rows: list[dict], chart: dict) -> dict:
    from app.services.geoReference import match_cities
    from app.services.chartValidation import build_match_rate_note

    print("MAP DEBUG sql:", chart.get("sql"))
    print("MAP DEBUG granularity:", chart.get("granularity"))
    print("MAP DEBUG rows sample:", rows[:5])

    title = chart.get("chart_title", "")
    x_alias, y_alias = chart.get("x_alias"), chart.get("y_alias")
    _require_aliases(ChartType.MAP, x_alias, y_alias, title)

    country = chart.get("country")
    if not country:
        raise ValueError(f"Map chart missing country ({title})")

    match_result = await match_cities(pool, rows, x_alias, country, chart.get("granularity", "city"))

    print("MAP DEBUG matched_count/total:", match_result["matched_count"], "/", match_result["total_count"])
    print("MAP DEBUG matched sample:", match_result["rows"][:5])

    matched_rows = [r for r in match_result["rows"] if r["match_status"] == "matched"]

    if not matched_rows:
        raise ValueError(f"No cities could be matched for map chart ({title})")

    raw = [_row_value(r, y_alias, title) for r in matched_rows]
    values = [v if isinstance(v, (int, float)) and v > 0 else 0 for v in raw]
    scaled = [math.sqrt(v) for v in values]
    peak = max(scaled)
    max_marker_size = 40
    sizeref = (2 * peak / (max_marker_size ** 2)) if peak > 0 else 1

    y_display = chart.get("y_label") or y_alias

    trace = {
        "type": "scattermap",
        "mode": "markers",
        "lat": [r["lat"] for r in matched_rows],
        "lon": [r["lon"] for r in matched_rows],
        "text": [f"{_row_value(r, x_alias, title)}<br>{y_display}: {_row_value(r, y_alias, title)}" for r in matched_rows],
        "hovertemplate": "%{text}<extra></extra>",
        "marker": {
            "size": scaled,
            "sizemode": "area",
            "sizeref": sizeref,
            "sizemin": 4,
        },
    }

    lats = [r["lat"] for r in matched_rows]
    lons = [r["lon"] for r in matched_rows]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2

    span = max(max(lats) - min(lats), max(lons) - min(lons), 0.01)
    zoom = max(2, min(8, 8 - span / 10))

    layout = {
        "title": {"text": title},
        "map": {
            "style": "open-street-map",
            "center": {"lat": center_lat, "lon": center_lon},
            "zoom": zoom,
        },
    }
    layout["map"]["layers"] = [{
        "source": _load_india_border_geojson(),
        "type": "line",
        "color": "#B092AD",
        "line": {"width": 1},
    }]
    #B092AD
    
    note = build_match_rate_note(match_result["matched_count"], match_result["total_count"])
    if note:
        layout["annotations"] = [{"text": note, "showarrow": False, "x": 0, "y": -0.1, "xref": "paper", "yref": "paper"}]

    return {"rows": matched_rows, "spec": {"data": [trace], "layout": layout}}

def _substitute_row_values(node, row: dict):
    # LLM authors viz_params before the query runs, so it can't know
    # computed values (e.g. AVG(price)) at write time — it writes the
    # SQL alias name as a string placeholder instead (same pattern as
    # x_alias/y_alias elsewhere). Walk the structure and swap any string
    # leaf that matches a row column name for the real computed value.
    if isinstance(node, dict):
        return {k: _substitute_row_values(v, row) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute_row_values(v, row) for v in node]
    if isinstance(node, str) and node in row:
        return _sanitize_numeric(row[node])
    return node

def _passthrough_trace(chart_type: ChartType, chart: dict, rows: list[dict], title: str) -> dict:
    viz_params = chart.get("viz_params")
    if not viz_params or not isinstance(viz_params, dict):
        raise ValueError(f"viz_params (non-empty dict) required for chart type '{chart_type.value}' ({title})")

    viz_params = _substitute_row_values(viz_params, rows[0])

    required = CHART_TYPE_REGISTRY[chart_type]["viz_params_required_keys"]
    missing = [k for k in required if k not in viz_params]
    if missing:
        raise ValueError(
            f"viz_params missing required key(s) {missing} for chart type "
            f"'{chart_type.value}' ({title}). Expected keys: {required}."
        )

    trace = dict(viz_params)
    trace.setdefault("type", CHART_TYPE_REGISTRY[chart_type]["plotly_type"])
    return trace