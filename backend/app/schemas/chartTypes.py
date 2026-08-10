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
    SANKEY = "sankey"
    PIVOT = "pivot"    
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
SERIES_CAPABLE_TYPES = {ChartType.BAR, ChartType.ROW, ChartType.LINE, ChartType.SCATTER, ChartType.HISTOGRAM}
# Single raw numeric column, one row per record — not GROUP BY reduced.
# Plotly bins the values into a distribution client-side.
HISTOGRAM_TYPES = {ChartType.HISTOGRAM}

# Single raw measure column (y_alias), optionally paired with a raw
# categorical column (x_alias) for one box per category. Not GROUP BY
# reduced — Plotly computes quartiles/outliers itself from the raw
# x/y arrays; repeated x values group into one box automatically.
DISTRIBUTION_TYPES = {ChartType.BOX}

# Three-column flow type: source category, target category, weight/count.
# Dasher builds the actual sankey node/link structure server-side from
# real rows (dedup labels, map to indices) — the LLM only picks which
# SQL columns are source/target/value, same trust model as x_alias/y_alias
# elsewhere. Hand-deriving node/link indices was tried and failed at
# real-world cardinality (15+ categories), so this isn't LLM-authored.
SANKEY_TYPES = {ChartType.SANKEY}

TIER_A_TYPES = (SCALAR_TYPES | NO_VIZ_SETTINGS_TYPES | DIMENSION_MEASURE_TYPES | MEASURE_PAIR_TYPES | HISTOGRAM_TYPES | DISTRIBUTION_TYPES | SANKEY_TYPES)



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

PASSTHROUGH_TYPES = {ChartType.GAUGE, ChartType.FUNNEL}

_UNSUPPORTED_TYPES = {ChartType.PIVOT}
CHART_TYPE_VALUES = [t.value for t in ChartType if t not in _UNSUPPORTED_TYPES]

CHART_TYPE_GUIDANCE = """- Measures stay numeric: never format a value into a display string in
  SQL ("2m 15s", "$1,200") — it breaks ORDER BY (sorts lexically) and
  turns the axis categorical (renders in row order, not numeric order).
  For units, use x_label/y_label instead — e.g. x_label:
  "Resolution Time (hours)" while x_alias stays "resolution_hours" and
  the SQL returns the raw number. (Pie has no x/y axes — x_label/y_label
  don't apply there, the dimension's own values are the labels.)
- scalar: query returns exactly one row, one column. No extra config needed.
- bar, row, line, pie: first column is a dimension, second is a measure.
  (row = horizontal bar, better for long category labels.)
  pie represents part-of-whole share and works best with few categories;
  prefer bar over pie for precise magnitude comparison.
- scatter: both columns are continuous measures — use for correlation
  between two measures, not a time trend.
- table: result has more than two columns, or doesn't reduce cleanly to a
  single dimension + measure pair. No extra config needed.
- bar/row/line/scatter/histogram can take a series_alias — a second
  dimension to group by within each category (groups/stacks for
  bar/row/line, separate colored traces for scatter, overlaid
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
"""