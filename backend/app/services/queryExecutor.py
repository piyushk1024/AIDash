import logging
from app.services.sqlGuard import validate_sql
from app.schemas.chartTypes import (
    ChartType,
    DIMENSION_MEASURE_TYPES,
    MEASURE_PAIR_TYPES,
    SERIES_CAPABLE_TYPES,
    PASSTHROUGH_TYPES,
)

logger = logging.getLogger(__name__)

_PASSTHROUGH_PLOTLY_TYPE = {
    ChartType.GAUGE: "indicator",
    ChartType.FUNNEL: "funnel",
    ChartType.WATERFALL: "waterfall",
    ChartType.MAP: "choroplethmapbox",
}


async def execute_chart_query(pool, chart: dict) -> dict:
    """
    Runs chart["sql"] through sqlGuard, executes it against the pool, and
    builds a Plotly spec (data + layout) from the result rows and chart_type.

    Returns {"rows": [...], "spec": {"data": [...], "layout": {...}}}.
    Raises ValueError on validation, execution, or shape errors — caller
    (cardBuilder) is expected to route these through the existing
    self-healing retry cycle.
    """
    validate_sql(chart["sql"], context=chart.get("chart_title", ""))

    async with pool.acquire() as conn:
        records = await conn.fetch(chart["sql"])
    rows = [dict(r) for r in records]

    spec = _build_plotly_spec(rows, chart)
    return {"rows": rows, "spec": spec}


async def execute_raw_query(pool, sql: str) -> dict:
    """
    Executes raw SQL and returns rows only, no spec building. Used by
    inspect_data (agent) and insight generation, where the caller has
    already validated the SQL via sqlGuard and just wants result rows
    to reason over — not a chart to render.
    """
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


def _build_plotly_spec(rows: list[dict], chart: dict) -> dict:
    chart_type = ChartType(chart["chart_type"])
    title = chart.get("chart_title", "")
    layout = {"title": title}

    if chart_type in PASSTHROUGH_TYPES:
        trace = _passthrough_trace(chart_type, chart, title)
        return {"data": [trace], "layout": layout}

    if not rows:
        raise ValueError(f"Query returned no rows ({title})")

    if chart_type == ChartType.SCALAR:
        value = next(iter(rows[0].values()))
        return {"data": [{"type": "indicator", "mode": "number", "value": value}], "layout": layout}

    if chart_type == ChartType.TABLE:
        columns = list(rows[0].keys())
        trace = {
            "type": "table",
            "header": {"values": columns},
            "cells": {"values": [[row[col] for row in rows] for col in columns]},
        }
        return {"data": [trace], "layout": layout}

    if chart_type in MEASURE_PAIR_TYPES:
        x_alias, y_alias = chart.get("x_alias"), chart.get("y_alias")
        _require_aliases(chart_type, x_alias, y_alias, title)
        trace = {
            "type": "scatter",
            "mode": "markers",
            "x": [_row_value(r, x_alias, title) for r in rows],
            "y": [_row_value(r, y_alias, title) for r in rows],
        }
        return {"data": [trace], "layout": layout}

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
        return {"data": data, "layout": layout}

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
    raise ValueError(f"No trace builder for chart type '{chart_type.value}'")


def _grouped_traces(chart_type: ChartType, rows: list[dict], x_alias: str, y_alias: str, series_alias: str, title: str) -> list[dict]:
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
        y = [_row_value(r, y_alias, title) for r in group_rows]
        trace = _single_trace(chart_type, x, y)
        trace["name"] = str(key)
        traces.append(trace)
    return traces


def _passthrough_trace(chart_type: ChartType, chart: dict, title: str) -> dict:
    viz_params = chart.get("viz_params")
    if not viz_params or not isinstance(viz_params, dict):
        raise ValueError(f"viz_params (non-empty dict) required for chart type '{chart_type.value}' ({title})")
    trace = dict(viz_params)
    trace.setdefault("type", _PASSTHROUGH_PLOTLY_TYPE[chart_type])
    return trace