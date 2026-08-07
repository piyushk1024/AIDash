from enum import Enum


class ChartType(str, Enum):
    """
    Single source of truth for chart types Dasher can request from Metabase.

    Consumed by: agentTools.py (tool schema enum + prompt), dashboardPlanner.py,
    selfHealer.py, nlChartBuilder.py (prompt text), and metabaseClient.py
    (visualization_settings construction).

    Adding a value here does not automatically make it usable end-to-end —
    metabaseClient.create_card() must also know how to build (or accept)
    visualization_settings for it. See TIER_A / TIER_B below.
    """
    SCALAR = "scalar"
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    ROW = "row"
    TABLE = "table"
    GAUGE = "gauge"
    FUNNEL = "funnel"
    WATERFALL = "waterfall"
    PIVOT = "pivot"
    MAP = "map"
    HISTOGRAM = "histogram"
    BOX = "box"


# ── Tier A — structured params ───────────────────────────────
# Dasher builds visualization_settings itself from x_alias / y_alias
# (and, for series-capable types, an optional series_alias). The LLM
# never hand-writes Metabase viz JSON for these — it just picks a type
# and aliases its SQL output columns.

SCALAR_TYPES = {ChartType.SCALAR}

# No visualization_settings needed at all — Metabase infers columns
# directly from the query result.
NO_VIZ_SETTINGS_TYPES = {ChartType.SCALAR, ChartType.TABLE}

# Single dimension + single measure (graph.dimensions / graph.metrics).
DIMENSION_MEASURE_TYPES = {ChartType.BAR, ChartType.LINE, ChartType.PIE, ChartType.ROW}

# Two continuous measures plotted against each other rather than a
# dimension against a measure. Uses x_alias/y_alias the same way, but
# both aliases refer to measures, not a category + aggregate.
MEASURE_PAIR_TYPES = {ChartType.SCATTER}

# Types that additionally accept an optional second breakout dimension
# for grouped/stacked rendering (graph.dimensions gets a second entry).
SERIES_CAPABLE_TYPES = {ChartType.BAR, ChartType.ROW}
# Single raw numeric column, one row per record — not GROUP BY reduced.
# Plotly bins the values into a distribution client-side.
HISTOGRAM_TYPES = {ChartType.HISTOGRAM}

# Single raw measure column (y_alias), optionally paired with a raw
# categorical column (x_alias) for one box per category. Not GROUP BY
# reduced — Plotly computes quartiles/outliers itself from the raw
# x/y arrays; repeated x values group into one box automatically.
DISTRIBUTION_TYPES = {ChartType.BOX}

TIER_A_TYPES = (SCALAR_TYPES | NO_VIZ_SETTINGS_TYPES | DIMENSION_MEASURE_TYPES | MEASURE_PAIR_TYPES | HISTOGRAM_TYPES | DISTRIBUTION_TYPES)



# ── Tier B — generic passthrough ─────────────────────────────
# The shape of visualization_settings varies per instance (which
# percentile bands, which stage order, which columns split into rows
# vs. columns), so Dasher does not pre-build it. The LLM supplies
# viz_params directly — a dict matching what Metabase expects for that
# display type — and Dasher does light shape validation, not full
# re-derivation. Metabase render failures route through the existing
# self-healing cycle same as any other chart error.

# PIVOT excluded: Metabase only supports pivot tables for GUI query-builder
# cards, never native SQL cards, which is what Dasher always sends.

PASSTHROUGH_TYPES = {ChartType.GAUGE, ChartType.FUNNEL, ChartType.WATERFALL, ChartType.MAP}

_UNSUPPORTED_TYPES = {ChartType.PIVOT}
CHART_TYPE_VALUES = [t.value for t in ChartType if t not in _UNSUPPORTED_TYPES]

CHART_TYPE_GUIDANCE = """- scalar: query returns exactly one row, one column. No extra config needed.
- bar, row, line, pie: first column is a dimension, second is a measure.
  (row = horizontal bar, better for long category labels.)
  pie represents part-of-whole share and works best with few categories;
  when the goal is comparing magnitudes precisely across categories, bar
  is usually the safer default.
- scatter: both columns are continuous measures — use for correlation
  between two measures, not a time trend.
- table: result has more than two columns, or doesn't reduce cleanly to a
  single dimension + measure pair. No extra config needed.
- bar/row can optionally take a series_alias — a second dimension to
  group or stack by within each category (e.g. compare two segments
  side by side within the same chart, instead of building two charts).
- gauge, funnel, waterfall, pivot, map need viz_params: a dict you build
  yourself, matching what that chart type needs. You decide the values
  via your own SQL — e.g. for gauge, compute percentile or threshold
  bands with a query, then supply them as segments; for pivot, decide
  which columns are rows vs. columns vs. values. Dasher does not compute
  these for you and will not second-guess reasonable values you provide.
- histogram: one raw numeric column, one row per record — do not GROUP BY,
  return the column directly, aliased as x_alias. Use to show the
  distribution/shape of a single measure (e.g. order value spread).
  Plotly bins client-side, so it doesn't need pre-aggregation. Add a
  reasonable LIMIT (e.g. 5000) if the table is large.
- box: one raw numeric column (y_alias), one row per record, optionally
  paired with a raw categorical column (x_alias) for one box per
  category. Do not GROUP BY or pre-compute percentiles — Plotly derives
  quartiles and outliers itself from the raw values. Add a LIMIT if the
  table is large, same as histogram.
"""