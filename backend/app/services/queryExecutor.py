import logging
from app.services.sqlGuard import validate_sql
from app.schemas.chartTypes import (
    ChartType,
    DIMENSION_MEASURE_TYPES,
    MEASURE_PAIR_TYPES,
    SERIES_CAPABLE_TYPES,
    PASSTHROUGH_TYPES,
    HISTOGRAM_TYPES,
    DISTRIBUTION_TYPES,
    SANKEY_TYPES,
)

logger = logging.getLogger(__name__)

_PASSTHROUGH_PLOTLY_TYPE = {
    ChartType.GAUGE: "indicator",
    ChartType.FUNNEL: "funnel",    
}

ROW_CHART_CAP = 15


ROW_CHART_CAP = 15

def _cap_tabular_rows(rows: list[dict], chart: dict) -> list[dict]:
    """Row (horizontal bar) and table charts show individual records/categories,
    not raw data dumps — cap to top N so cards/modal/exports never need to
    scroll or clip. Sorts by y_alias descending when present (row charts,
    ranking by measure); table charts have no y_alias, so this just takes
    the first N in query order. Falls back to a plain slice if y_alias is
    missing or non-numeric (avoids crashing the chart over a sort issue,
    capped output still beats an uncapped one)."""
    y_alias = chart.get("y_alias")
    if y_alias:
        try:
            rows = sorted(rows, key=lambda r: r.get(y_alias) or 0, reverse=True)
        except TypeError:
            pass
    return rows[:ROW_CHART_CAP]

async def execute_chart_query(pool, chart: dict, table_name: str) -> dict:
    """
    Runs chart["sql"] through sqlGuard, executes it against the pool, and
    builds a Plotly spec (data + layout) from the result rows and chart_type.

    Returns {"rows": [...], "spec": {"data": [...], "layout": {...}}}.
    Raises ValueError on validation, execution, or shape errors — caller
    (cardBuilder) is expected to route these through the existing
    self-healing retry cycle.
    """
    validate_sql(chart["sql"], table_name, context=chart.get("chart_title", ""))

    async with pool.acquire() as conn:
        records = await conn.fetch(chart["sql"])
    rows = [dict(r) for r in records]
    if chart.get("chart_type") in (ChartType.ROW.value, ChartType.TABLE.value):
        rows = _cap_tabular_rows(rows, chart)

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
    return row[alias]

def _axis_title(chart: dict, label_key: str, alias_fallback: str | None) -> dict:
    # Prefers the LLM-authored x_label/y_label (human-readable, can carry
    # units) over the raw SQL alias. Falls back to the alias so no existing
    # plan breaks if the label field is absent — same backward-compat
    # pattern as every other optional chart field (series_alias, etc.).
    label = chart.get(label_key)
    return {"title": {"text": label or alias_fallback}}
def _round_if_float(value, ndigits: int = 2):
    """Round floats for display; leave ints, strings, dates, None untouched."""
    if isinstance(value, float):
        return round(value, ndigits)
    return value

def _build_plotly_spec(rows: list[dict], chart: dict) -> dict:
    chart_type = ChartType(chart["chart_type"])
    title = chart.get("chart_title", "")
    layout = {"title": {"text": title}}

    if not rows:
            raise ValueError(f"Query returned no rows ({title})")

    if chart_type == ChartType.SCALAR:
        value = _round_if_float(next(iter(rows[0].values())))
        return {"data": [{"type": "indicator", "mode": "number", "value": value}], "layout": layout}

    if chart_type == ChartType.TABLE:
        columns = list(rows[0].keys())
        trace = {
            "type": "table",
            "header": {"values": columns},
            "cells": {"values": [[_round_if_float(row[col]) for row in rows] for col in columns]},
        }
        return {"data": [trace], "layout": layout}

    if chart_type in MEASURE_PAIR_TYPES:
        x_alias, y_alias = chart.get("x_alias"), chart.get("y_alias")
        _require_aliases(chart_type, x_alias, y_alias, title)
        series_alias = chart.get("series_alias") if chart_type in SERIES_CAPABLE_TYPES else None

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

    if chart_type in DIMENSION_MEASURE_TYPES:
        x_alias, y_alias = chart.get("x_alias"), chart.get("y_alias")
        _require_aliases(chart_type, x_alias, y_alias, title)        
        series_alias = chart.get("series_alias") if chart_type in SERIES_CAPABLE_TYPES else None

        if series_alias:
            data = _grouped_traces(chart_type, rows, x_alias, y_alias, series_alias, title)
            layout["barmode"] = "group"
        else:
            x = [_row_value(r, x_alias, title) for r in rows]
            y = [_row_value(r, y_alias, title) for r in rows]
            data = [_single_trace(chart_type, x, y)]

        # ROW charts flip x/y internally (see _single_trace) — axis titles
        # follow the same swap so labels stay on the correct axis.
        if chart_type == ChartType.ROW:
            # ROW flips x/y in the trace itself (see _single_trace) — the
            # label follows the same swap, since y_label describes the
            # measure and ROW plots the measure on the x-axis.
            layout["xaxis"] = _axis_title(chart, "y_label", y_alias)
            layout["yaxis"] = _axis_title(chart, "x_label", x_alias)
            layout["xaxis"]["rangemode"] = "tozero"
        elif chart_type != ChartType.PIE:
            layout["xaxis"] = _axis_title(chart, "x_label", x_alias)
            layout["yaxis"] = _axis_title(chart, "y_label", y_alias)
        return {"data": data, "layout": layout}

    if chart_type in HISTOGRAM_TYPES:
        x_alias = chart.get("x_alias")
        if not x_alias:
            raise ValueError(f"x_alias required for chart type '{chart_type.value}' ({title})")
        series_alias = chart.get("series_alias") if chart_type in SERIES_CAPABLE_TYPES else None

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

    if chart_type in DISTRIBUTION_TYPES:
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
    
    if chart_type in SANKEY_TYPES:
        trace = _build_sankey_trace(rows, chart, title)
        return {"data": [trace], "layout": layout}
    
    if chart_type in PASSTHROUGH_TYPES:
        trace = trace = _passthrough_trace(chart_type, chart, rows, title)
        return {"data": [trace], "layout": layout}  

    raise ValueError(f"Unsupported chart type '{chart_type.value}' ({title})")

def _require_aliases(chart_type: ChartType, x_alias, y_alias, title: str) -> None:
    if not x_alias or not y_alias:
        raise ValueError(f"x_alias/y_alias required for chart type '{chart_type.value}' ({title})")


def _single_trace(chart_type: ChartType, x: list, y: list) -> dict:
    if chart_type == ChartType.BAR:
        return {"type": "bar", "x": x, "y": y}
    if chart_type == ChartType.ROW:
        return {"type": "bar", "x": y, "y": x, "orientation": "h"}
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

_PASSTHROUGH_REQUIRED_KEYS = {
    ChartType.GAUGE: ("domain", "gauge","value"),
    ChartType.FUNNEL: ("x", "y"),    
}


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
        return row[node]
    return node


def _passthrough_trace(chart_type: ChartType, chart: dict, rows: list[dict], title: str) -> dict:
    viz_params = chart.get("viz_params")
    if not viz_params or not isinstance(viz_params, dict):
        raise ValueError(f"viz_params (non-empty dict) required for chart type '{chart_type.value}' ({title})")

    viz_params = _substitute_row_values(viz_params, rows[0])

    required = _PASSTHROUGH_REQUIRED_KEYS[chart_type]
    missing = [k for k in required if k not in viz_params]
    if missing:
        raise ValueError(
            f"viz_params missing required key(s) {missing} for chart type "
            f"'{chart_type.value}' ({title}). Expected keys: {required}."
        )

    trace = dict(viz_params)
    trace.setdefault("type", _PASSTHROUGH_PLOTLY_TYPE[chart_type])
    return trace