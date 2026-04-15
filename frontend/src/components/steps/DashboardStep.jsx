export default function DashboardStep({ dasher, isActive, isExpanded, onToggle }) {
  const { createDashboard, status, errors, dashboardResult, plan } = dasher

  const isLoading = status.dashboard === 'loading'
  const isDone    = status.dashboard === 'done'

  if (isDone && dashboardResult) {
    return (
      <div className="animate-fade-in">
        <div className="w-full px-4 py-3 flex items-center gap-3 font-mono text-xs rounded border border-transparent">
          <span className="text-neutral-500 uppercase tracking-wider">Dashboard</span>
          <span className="text-neutral-300 dark:text-neutral-600">—</span>
          <span className="text-neutral-700 dark:text-neutral-300">{dashboardResult.cards_created} cards created</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <button
            onClick={createDashboard}
            disabled={isLoading}
            title="Rebuild dashboard"
            className="ml-2 font-mono text-xs text-neutral-400 hover:text-amber-400 transition-colors border border-neutral-200 dark:border-neutral-800 hover:border-amber-400/50 rounded px-2 py-0.5"
          >
            {isLoading ? '...' : 'rebuild'}
          </button>
        </div>
      </div>
    )
  }

  if (!isActive) return null

  return (
    <div className="animate-fade-in mt-6">
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/[0.02] dark:bg-amber-400/[0.03] px-6 py-5">
        <StepHeader title="Build Dashboard" />
        <p className="font-mono text-xs text-neutral-500 mt-1 mb-5">
          Creates the dashboard and all chart cards in Metabase via API.
        </p>

        {plan && (
          <div className="mb-5 p-4 border border-neutral-200 dark:border-neutral-800 rounded space-y-2 bg-white dark:bg-neutral-900">
            <div className="font-mono text-xs text-neutral-500 uppercase tracking-wider mb-2">
              Planned — {plan.charts.length} charts
            </div>
            {plan.charts.map(chart => (
              <div key={chart.chart_id} className="font-mono text-xs flex items-center gap-3">
                <span className={`border rounded px-1.5 py-0.5 text-[10px] uppercase
                  ${chart.chart_type === 'bar'    ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/5' : ''}
                  ${chart.chart_type === 'line'   ? 'border-blue-500/30    text-blue-400    bg-blue-500/5'    : ''}
                  ${chart.chart_type === 'scalar' ? 'border-amber-500/30   text-amber-400   bg-amber-500/5'   : ''}
                  ${chart.chart_type === 'pie'    ? 'border-violet-500/30  text-violet-400  bg-violet-500/5'  : ''}
                `}>
                  {chart.chart_type}
                </span>
                <span className="text-neutral-600 dark:text-neutral-400">{chart.chart_title}</span>
              </div>
            ))}
          </div>
        )}

        {errors.dashboard && (
          <div className="mb-3 font-mono text-xs text-red-400">✕ {errors.dashboard}</div>
        )}

        <div className="flex items-center gap-4">
          <button
            onClick={createDashboard}
            disabled={isLoading}
            className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-100 dark:disabled:bg-neutral-800 disabled:text-neutral-400 dark:disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer enabled:shadow-sm"
          >
            {isLoading ? 'Building...' : 'Build Dashboard'}
          </button>
          {isLoading && (
            <span className="font-mono text-xs text-neutral-500 animate-pulse">
              Creating cards in Metabase...
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function StepHeader({ title }) {
  return (
    <h2 className="font-mono text-sm tracking-widest uppercase text-neutral-900 dark:text-neutral-100 mb-1">
      {title}
    </h2>
  )
}