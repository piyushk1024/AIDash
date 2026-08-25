// Single source of truth for chart-type badge colors. Previously duplicated
// (and drifting) across NLAuthoringPanel.jsx, PlanStep.jsx, and
// DashboardStep.jsx's pre-build preview — each had a slightly different
// version
export const CHART_TYPE_BADGE = {
  bar:    'border-emerald-500/30 text-emerald-400 bg-emerald-500/5',
  // row:    'border-emerald-500/30 text-emerald-400 bg-emerald-500/5',
  line:   'border-blue-500/30    text-blue-400    bg-blue-500/5',
  scalar: 'border-amber-500/30   text-amber-400   bg-amber-500/5',
  pie:    'border-violet-500/30  text-violet-400  bg-violet-500/5',
}

export const CHART_TYPE_BADGE_FALLBACK = 'border-neutral-700 text-neutral-500 bg-neutral-800/20'

export function chartTypeBadgeClass(chartType) {
  return CHART_TYPE_BADGE[chartType] ?? CHART_TYPE_BADGE_FALLBACK
}