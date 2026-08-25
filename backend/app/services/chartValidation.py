"""
Validation for chart specs produced by any authoring path (pipeline plan,
agent tool calls, NL chart requests). Separate from chartTypes.py, which
is pure schema (what chart types exist and their properties) — this file
is business rules (is this specific chart instance acceptable).

Runs before a chart's SQL is ever executed. Unrelated to selfHealer.py,
which repairs a chart after a downstream execution failure — these two
never call each other.
"""

from app.schemas.chartTypes import CHART_TYPE_VALUES, ChartType, HISTOGRAM_TYPES


PIE_MAX_DISTINCT = 10
HISTOGRAM_MIN_DISTINCT = 15
CATEGORY_MAX_DISTINCT = 30
SERIES_MAX_DISTINCT = 10
SANKEY_NODE_MAX_DISTINCT = 15

def _distinct_count_for_alias(profile: dict, alias: str | None) -> int | None:
    # Cardinality/legibility guardrail lookup. Guidance instructs histogram/
    # box/pie/sankey source columns to use a SQL alias matching the source
    # column name, so a direct name match covers the normal case. Fails
    # open (returns None) on any mismatch rather than blocking a chart over
    # an alias the guardrail can't confidently resolve.
    if not alias:
        return None
    for col in profile.get("columns", []):
        if col.get("column_name") == alias:
            return col.get("distinct_count")
    return None


def apply_cardinality_guardrail(chart: dict, profile: dict | None) -> str | None:
    """Checks chart cardinality/legibility against profile.distinct_count.
    May mutate `chart` in place (pie -> bar downgrade, same SQL shape, no
    re-query needed). Returns a violation reason string if the chart should
    be rejected outright, else None. Fails open (returns None, no mutation)
    if profile is falsy — callers without a profile skip this guardrail
    rather than block on it."""
    if not profile:
        return None

    chart_type_str = chart.get("chart_type")
    if chart_type_str not in CHART_TYPE_VALUES:
        return None
    chart_type = ChartType(chart_type_str)

    x_distinct = _distinct_count_for_alias(profile, chart.get("x_alias"))

    if chart_type == ChartType.PIE and x_distinct is not None and x_distinct > PIE_MAX_DISTINCT:
        chart["chart_type"] = ChartType.BAR.value
        chart_type = ChartType.BAR

    if chart_type in HISTOGRAM_TYPES and x_distinct is not None and x_distinct < HISTOGRAM_MIN_DISTINCT:
        return f"x_alias '{chart.get('x_alias')}' has too few distinct values ({x_distinct}) for a histogram."

    if chart_type in (ChartType.BAR, ChartType.BOX) and x_distinct is not None and x_distinct > CATEGORY_MAX_DISTINCT:
        return f"x_alias '{chart.get('x_alias')}' has too many distinct values ({x_distinct}) to display legibly."

    series_distinct = _distinct_count_for_alias(profile, chart.get("series_alias"))
    if series_distinct is not None and series_distinct > SERIES_MAX_DISTINCT:
        return f"series_alias '{chart.get('series_alias')}' has too many distinct values ({series_distinct}) for a legible series split."

    if chart_type == ChartType.SANKEY:
        source_distinct = _distinct_count_for_alias(profile, chart.get("source_alias"))
        target_distinct = _distinct_count_for_alias(profile, chart.get("target_alias"))
        if (source_distinct is not None and source_distinct > SANKEY_NODE_MAX_DISTINCT) or \
           (target_distinct is not None and target_distinct > SANKEY_NODE_MAX_DISTINCT):
            return "sankey source/target nodes exceed max distinct node count."

    return None

def missing_required_fields(chart: dict, required: tuple[str, ...]) -> list[str]:
    """Returns the subset of `required` keys that are absent or falsy on
    `chart`. Empty list means all present. Shared by every chart-authoring
    path (pipeline, agent, NL) so the presence check doesn't drift between
    them — each path keeps its own required tuple and its own handling of
    a non-empty result (raise, drop, or return as a dispatch error)."""
    missing = []
    for field in required:
        # falsy check, not just "key absent" — an empty string counts as
        # missing too, since a blank value is as unusable as no key at all
        if not chart.get(field):
            missing.append(field)
    return missing


def clean_and_validate_charts(charts: list) -> list:
    """Drops charts with missing required fields, an unrecognised
    chart_type, or a duplicate title (first occurrence wins). Shared by
    dashboardRoute.py and pipelineOrchestrator.py — kept here rather than
    in either route file so neither takes a dependency on the other."""
    seen_titles = set()
    cleaned = []
    for chart in charts:
        if missing_required_fields(chart, ("sql", "chart_title", "chart_type")):
            continue
        if chart["chart_type"] not in CHART_TYPE_VALUES:
            continue
        if chart["chart_title"] in seen_titles:
            continue
        seen_titles.add(chart["chart_title"])
        cleaned.append(chart)
    return cleaned