from enum import Enum


class ChartType(str, Enum):
    """
    Single source of truth for chart types Dasher can request.

    Consumed by: agentTools.py (tool schema enum + prompt), dashboardPlanner.py,
    selfHealer.py, nlChartBuilder.py (prompt text), and queryExecutor.py
    (Plotly spec construction).

    Adding a value here does not automatically make it usable end-to-end —
    it also needs an entry in CHART_TYPE_REGISTRY below. See TIER_A / TIER_B.
    """
    SCALAR = "scalar"
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"    
    TABLE = "table"
    GAUGE = "gauge"
    FUNNEL = "funnel"
    SANKEY = "sankey"
    PIVOT = "pivot"
    HISTOGRAM = "histogram"
    BOX = "box"
    HEATMAP = "heatmap"
    MAP = "map"


# ── Registry — single source of truth per type ──────────────
# One record per usable chart type. Every membership set below is derived
# from this dict, not hand-maintained, so adding a type means adding one
# record here instead of updating N sets by hand.
#
# Fields:
#   category            — dispatch bucket used by queryExecutor._build_plotly_spec
#   required_aliases    — top-level chart fields that must be present (empty
#                          tuple if none, e.g. passthrough validates viz_params
#                          keys instead — see viz_params_required_keys)
#   series_capable       — accepts an optional series_alias for grouping
#   plotly_type          — trace "type" value. Authoritative for passthrough
#                          types (used directly); informational for the rest,
#                          which have per-type trace-building logic 
#   viz_params_required_keys — passthrough types only: required keys inside
#                          the LLM-authored viz_params dict, checked at
#                          render time (hoisted from queryExecutor.py's old
#                          _PASSTHROUGH_REQUIRED_KEYS, same shape, same values)
#
# query-builder cards, never native SQL cards, which is what Dasher always
# sends, so it stays permanently unsupported.

CHART_TYPE_REGISTRY = {
    ChartType.SCALAR: {
        "category": "scalar",
        "required_aliases": (),
        "series_capable": False,
        "plotly_type": "indicator",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.BAR: {
        "category": "dimension_measure",
        "required_aliases": ("x_alias", "y_alias"),
        "series_capable": True,
        "plotly_type": "bar",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.LINE: {
        "category": "dimension_measure",
        "required_aliases": ("x_alias", "y_alias"),
        "series_capable": True,
        "plotly_type": "scatter",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.PIE: {
        "category": "dimension_measure",
        "required_aliases": ("x_alias", "y_alias"),
        "series_capable": False,
        "plotly_type": "pie",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.SCATTER: {
        "category": "measure_pair",
        "required_aliases": ("x_alias", "y_alias"),
        "series_capable": True,
        "plotly_type": "scatter",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.TABLE: {
        "category": "table",
        "required_aliases": (),
        "series_capable": False,
        "plotly_type": "table",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.GAUGE: {
        "category": "passthrough",
        "required_aliases": (),
        "series_capable": False,
        "plotly_type": "indicator",
        "viz_params_required_keys": ("domain", "gauge", "value"),
         "requires_sql": True,
    },
    ChartType.FUNNEL: {
        "category": "passthrough",
        "required_aliases": (),
        "series_capable": False,
        "plotly_type": "funnel",
        "viz_params_required_keys": ("x", "y"),
         "requires_sql": True,
    },
    ChartType.SANKEY: {
        "category": "sankey",
        "required_aliases": ("source_alias", "target_alias", "value_alias"),
        "series_capable": False,
        "plotly_type": "sankey",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.HISTOGRAM: {
        "category": "histogram",
        "required_aliases": ("x_alias",),
        "series_capable": True,
        "plotly_type": "histogram",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.BOX: {
        "category": "distribution",
        "required_aliases": ("y_alias",),
        "series_capable": False,
        "plotly_type": "box",
        "viz_params_required_keys": None,
         "requires_sql": True,
    },
    ChartType.HEATMAP: {
        "category": "correlation",
        "required_aliases": (),
        "series_capable": False,
        "plotly_type": "heatmap",
        "viz_params_required_keys": None,
         "requires_sql": False,
    },
        ChartType.MAP: {
        "category": "map",
        "required_aliases": ("x_alias", "y_alias"),
        "series_capable": False,
        "plotly_type": "scattermap",
        "viz_params_required_keys": None,
        "requires_sql": True,
    },
}


# ── Derived sets — kept for backward compat ──────────────────
# Every consumer (queryExecutor.py, dashboardPlanner.py, etc.) imports these
# by name and checks membership the same way as before. Only the source of
# truth changed; the values are identical to the old hand-maintained sets.

SCALAR_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "scalar"}

NO_VIZ_SETTINGS_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] in ("scalar", "table")}

DIMENSION_MEASURE_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "dimension_measure"}

MEASURE_PAIR_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "measure_pair"}

SERIES_CAPABLE_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["series_capable"]}

HISTOGRAM_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "histogram"}

DISTRIBUTION_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "distribution"}

SANKEY_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "sankey"}

PASSTHROUGH_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "passthrough"}

CORRELATION_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "correlation"}

NO_SQL_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if not r["requires_sql"]}

MAP_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] == "map"}

# Everything with structured params Dasher builds itself — i.e. every
# registered type except passthrough (which the LLM hand-writes viz_params
# for) and PIVOT (unsupported, has no registry entry at all).
TIER_A_TYPES = {t for t, r in CHART_TYPE_REGISTRY.items() if r["category"] != "passthrough"}

# Iterates ChartType (not the registry) to preserve the original enum-order
# list; PIVOT is excluded because it has no registry entry.
CHART_TYPE_VALUES = [t.value for t in ChartType if t in CHART_TYPE_REGISTRY]

CHART_TYPE_GUIDANCE = """- Measures stay numeric: never format a value into a display string in
  SQL ("2m 15s", "$1,200") — it breaks ORDER BY (sorts lexically) and
  turns the axis categorical (renders in row order, not numeric order).
  For units, use x_label/y_label instead — e.g. x_label:
  "Resolution Time (hours)" while x_alias stays "resolution_hours" and
  the SQL returns the raw number. (Pie has no x/y axes — x_label/y_label
  don't apply there, the dimension's own values are the labels.)
- scalar: query returns exactly one row, one column. No extra config needed.
- bar, line, pie: first column is a dimension, second is a measure.  
  pie represents part-of-whole share and works best with few categories;
  prefer bar over pie for precise magnitude comparison.
- scatter: both columns are continuous measures — use for correlation
  between two measures, not a time trend.
- table: result has more than two columns, or doesn't reduce cleanly to a
  single dimension + measure pair. No extra config needed.
- bar/line/scatter/histogram can take a series_alias — a second
  dimension to group by within each category (groups/stacks for
  bar/line, separate colored traces for scatter, overlaid
  semi-transparent distributions for histogram).
  MANDATORY: if your SQL GROUPs BY two dimension columns, series_alias
  must be set to the second one — the chart cannot show data it isn't
  told about. If a chart only needs one dimension, group by only one
  and leave series_alias out.
- gauge needs viz_params matching Plotly's gauge shape. domain is always
  {"x": [0, 1], "y": [0, 1]} (page position, unrelated to data).
  gauge.axis.range must be the real data's min/max from your own SQL —
  never reuse domain's [0, 1] or an arbitrary round number. Example, for
  an average price metric around 9.5 (lakhs):
    value = 9.5
    gauge = {"axis": {"range": [0, 15]}}   # derived from real MAX
    domain = {"x": [0, 1], "y": [0, 1]}
    mode = "gauge+number"
- funnel needs viz_params matching Plotly's funnel shape: y = ordered
  stage labels (top-to-bottom order matters), x = matching counts per
  stage. Only use for a genuine sequential process where each stage is a
  subset of the last (signup -> activation -> purchase). Do NOT use for
  categorical breakdowns that merely sort by count (dismissal type,
  region) — those belong in bar even if counts happen to decrease. If
  unsure whether a breakdown is a real process, default to bar.
- sankey: use source_alias (category), target_alias (category),
  value_alias (count/weight). Dasher derives node/link structure from
  your query results — don't build it yourself. GROUP BY the two
  categorical columns and aggregate a count/sum, e.g.:
    SELECT col_a AS source_alias, col_b AS target_alias, COUNT(*) AS value_alias
    FROM t GROUP BY col_a, col_b
- histogram: one raw numeric column, one row per record — do not GROUP BY.
  SELECT "price" AS price, set x_alias to that alias. Plotly bins
  client-side. If the table is large, ORDER BY RANDOM() LIMIT 5000
  rather than a bare LIMIT (a bare LIMIT isn't a random sample and skews
  the distribution).
- box: one raw numeric column, one row per record, optionally paired with
  a raw categorical column for one box per category. y_alias = numeric
  column, x_alias = categorical column. Do not GROUP BY or pre-compute
  percentiles — Plotly derives quartiles/outliers from raw values. Same
  ORDER BY RANDOM() LIMIT 5000 guidance as histogram if the table is large.
- heatmap: correlation matrix computed automatically from profiled data
  server-side. Do NOT write SQL for this — leave sql empty/null. No
  x_alias/y_alias/viz_params needed. Optionally set columns to a list of
  specific numeric column names for a focused matrix (e.g. columns:
  ["price", "rating", "reviews"]); omit columns for the full matrix across
  all numeric columns. Use only when the user explicitly asks for a
  correlation matrix or heatmap, optionally scoped to named columns.
"""

MAP_GUIDANCE = """- map: first column is a dimension (x_alias), second is a measure
  (y_alias) sized as bubble radius. Set the top-level "granularity" field
  to "city" or "state" based on what the user asked for — this is
  separate from and unrelated to anything inside your SQL.

  City-level (top-level granularity: "city"): x_alias is a raw city-name
  column from the data, not aggregated or renamed beyond a simple GROUP
  BY alias.
    SELECT city AS city_name, SUM(revenue) AS total_revenue
    FROM "{table}" GROUP BY city

  State-level, data already has a state column (top-level granularity:
  "state"): group by that column directly, same as city-level.
    SELECT state AS state_name, SUM(revenue) AS total_revenue
    FROM "{table}" GROUP BY state

  State-level, data only has city (top-level granularity: "state"):
  resolve state by joining the city column against a reference table of
  known cities, then GROUP BY the resolved state. Note the reference
  table's own rows are looked up at city grain internally — this has no
  bearing on your top-level "granularity" field, which is still "state"
  because that's what the finished chart shows.
    SELECT ref.state AS state_name, SUM(t.revenue) AS total_revenue
    FROM "{table}" t
    JOIN geo_reference ref
      ON ref.granularity = 'city' AND ref.country = '{country}'
      AND lower(t.city) = ref.name
    GROUP BY ref.state

  Use whatever aggregation fits the request (SUM, AVG, COUNT, MAX, etc.)
  — these are illustrative, not fixed. geo_reference is the only table
  besides the dataset's own table you may reference.
"""