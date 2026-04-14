export default function DashboardStep({ dasher, isActive, isExpanded, onToggle }) {
  const { createDashboard, status, errors, dashboardResult, plan } = dasher

  const isLoading = status.dashboard === 'loading'
  const isDone    = status.dashboard === 'done'

  // ── Done — collapsed summary with expand toggle ──
 if (isDone && dashboardResult) {
  return (
    <div className="animate-fade-in mt-6">
      <div className="w-full py-2 flex items-center gap-3 font-mono text-xs text-left">
        <button onClick={onToggle} className="flex items-center gap-3 flex-1 hover:opacity-80 transition-opacity">
          <span className="text-neutral-500 uppercase tracking-wider">Build Dashboard</span>
          <span className="text-neutral-600">—</span>
          <span className="text-neutral-400">{dashboardResult.cards_created} cards created</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <span className={`text-neutral-600 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
            ▾
          </span>
        </button>
        <button
          onClick={createDashboard}
          disabled={isLoading}
          className="font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors"
        >
          {isLoading ? '...' : '[ rebuild ]'}
        </button>
      </div>

        {isExpanded && (
          <div className="animate-fade-in mb-4 space-y-4">
            {/* Metabase link */}
            <a
              href={dashboardResult.dashboard_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 border border-amber-400/40 rounded font-mono text-xs text-amber-400 hover:bg-amber-400/10 transition-colors"
            >
              Open in Metabase ↗
            </a>

            {/* Cards created */}
            {dashboardResult.cards?.length > 0 && (
              <div className="space-y-1">
                {dashboardResult.cards.map(card => (
                  <div key={card.card_id} className="font-mono text-xs flex items-center gap-3">
                    <span className="text-neutral-600">#{card.card_id}</span>
                    <span className="text-neutral-400">{card.chart_title}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Errors if any cards failed */}
            {dashboardResult.errors?.length > 0 && (
              <div className="space-y-1">
                <div className="font-mono text-xs text-neutral-500 uppercase tracking-wider mb-1">
                  Failed
                </div>
                {dashboardResult.errors.map((e, i) => (
                  <div key={i} className="font-mono text-xs text-red-400">
                    ✕ {e.chart_title} — {e.error}
                  </div>
                ))}
              </div>
            )}

            {/* Metabase iframe embed */}
            <div className="mt-2">
              <div className="font-mono text-xs text-neutral-500 uppercase tracking-wider mb-2">
                Preview
              </div>
                <iframe
                  src={dashboardResult.public_url}
                  title="Metabase Dashboard"
                  className="w-full rounded border border-neutral-800"
                  style={{ height: '520px' }}
                />
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Not active yet ──
  if (!isActive) return null

  return (
    <div className="animate-fade-in mt-12">
      <StepHeader title="Build Dashboard" />

      <p className="font-mono text-xs text-neutral-500 mt-2 mb-6">
        Creates the dashboard and all chart cards in Metabase via API.
      </p>

      {/* Chart count from plan */}
      {plan && (
        <div className="mb-6 p-4 border border-neutral-800 rounded space-y-2">
          <div className="font-mono text-xs text-neutral-500 uppercase tracking-wider mb-2">
            Planned
          </div>
          {plan.charts.map(chart => (
            <div key={chart.chart_id} className="font-mono text-xs flex items-center gap-3">
              {/* Chart type badge */}
              <span className={`
                border rounded px-1.5 py-0.5 text-[10px] uppercase
                ${chart.chart_type === 'bar'    ? 'border-emerald-500/30 text-emerald-400' : ''}
                ${chart.chart_type === 'line'   ? 'border-blue-500/30    text-blue-400'    : ''}
                ${chart.chart_type === 'scalar' ? 'border-amber-500/30   text-amber-400'   : ''}
                ${chart.chart_type === 'pie'    ? 'border-violet-500/30  text-violet-400'  : ''}
              `}>
                {chart.chart_type}
              </span>
              <span className="text-neutral-400">{chart.chart_title}</span>
            </div>
          ))}
        </div>
      )}

      {errors.dashboard && (
        <div className="mb-3 font-mono text-xs text-red-400">
          ✕ {errors.dashboard}
        </div>
      )}

      <button
        onClick={createDashboard}
        disabled={isLoading}
        className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200
          disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed
          enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
      >
        {isLoading ? 'Building...' : 'Build Dashboard →'}
      </button>

      {isLoading && (
        <div className="mt-3 font-mono text-xs text-neutral-500 animate-pulse">
          Creating cards in Metabase...
        </div>
      )}
    </div>
  )
}

function StepHeader({ title, done }) {
  return (
    <div className="flex items-center gap-3 mb-2">
      <h2 className="font-mono text-sm tracking-widest uppercase text-neutral-900 dark:text-neutral-100">
        {title}
      </h2>
      {done && <span className="font-mono text-xs text-amber-400">✓ done</span>}

    </div>
  )
}