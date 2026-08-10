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
- bar/row/line/scatter/histogram can optionally take a series_alias — a
  second dimension to group by within each category. For bar/row/line
  this groups/stacks; for scatter it colors points by group into
  separate traces; for histogram it overlays semi-transparent
  distributions per group instead of one combined histogram.
- gauge needs viz_params matching Plotly's gauge indicator shape. The
  axis.range MUST reflect the real data scale, not [0, 1] and not an
  arbitrary round number — domain and axis.range are different things:
  domain positions the chart on the page and is always {"x": [0, 1],
  "y": [0, 1]}, axis.range is the data's min/max and must come from your
  own SQL (e.g. MIN/MAX of the measure, or known profile bounds). Do NOT
  reuse the domain's [0, 1] for axis.range.
  Example, for an average price metric around 9.5 (lakhs):
    value = 9.5
    gauge = {"axis": {"range": [0, 15]}}   # derived from real MAX, not [0,1]
    domain = {"x": [0, 1], "y": [0, 1]}    # always this, unrelated to data
    mode = "gauge+number"
- funnel needs viz_params matching Plotly's funnel trace shape:
  y = ordered stage labels (list, top-to-bottom order matters),
  x = matching counts/values for each stage (same length and order as y).
  Only use funnel when the categories represent a genuine sequential
  process where each stage is a subset of the one before it (e.g.
  signup -> activation -> purchase, or Owner_Type as 1st -> 2nd -> 3rd
  owner, where each stage necessarily has fewer records than the last).
  Do NOT use funnel for mutually exclusive categorical breakdowns that
  merely happen to sort by count (e.g. dismissal type, product category,
  region) — those are not a drop-off sequence and belong in bar instead,
  even if the counts happen to decrease. If you're unsure whether a
  breakdown is a real process, default to bar.
- sankey: use three column aliases — source_alias (category), target_alias
  (category), value_alias (count/weight for that source-target pair).
  Do NOT build node/link structures yourself; Dasher derives the node
  list and index mapping from your query results. Just GROUP BY the two
  categorical columns and aggregate a count/sum as the third, same as
  you would for any two-dimension breakdown, e.g.:
    SELECT col_a AS source_alias, col_b AS target_alias, COUNT(*) AS value_alias
    FROM t GROUP BY col_a, col_b
- histogram: one raw numeric column, one row per record — do not GROUP BY,
  return the column directly with a descriptive SQL alias (e.g.
  SELECT "price" AS price), then set x_alias in your JSON output to
  that same alias. Use to show the distribution/shape of a single
  measure (e.g. order value spread). Plotly bins client-side, so it
  doesn't need pre-aggregation. Add a reasonable LIMIT (e.g. 5000) if
  the table is large.
- box: one raw numeric column, one row per record, optionally paired
  with a raw categorical column for one box per category. Give both
  columns descriptive SQL aliases (e.g. SELECT "price" AS price,
  "fuel_type" AS fuel_type), then set y_alias to the numeric column's
  alias and x_alias to the categorical column's alias in your JSON
  output. Do not GROUP BY or pre-compute percentiles — Plotly derives
  quartiles and outliers itself from the raw values. Add a LIMIT if the
  table is large, same as histogram.
"""