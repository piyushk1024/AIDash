export default function PlanStep({ dasher, isActive, isExpanded, onToggle }) {
  const { generatePlan, status, errors, plan } = dasher

  const isLoading = status.plan === 'loading'
  const isDone    = status.plan === 'done'

  if (isDone && plan) {
    return (
      <div className="animate-fade-in">
        <button
          onClick={onToggle}
          className="w-full px-4 py-3 flex items-center gap-3 font-mono text-xs text-left rounded border border-transparent hover:border-neutral-200 dark:hover:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900 transition-all duration-150 cursor-pointer"
          title="Click to expand"
        >
          <span className="text-neutral-500 uppercase tracking-wider">Plan</span>
          <span className="text-neutral-300 dark:text-neutral-600">—</span>
          <span className="text-neutral-700 dark:text-neutral-300">{plan.charts.length} charts</span>
          <span className="text-neutral-400 truncate max-w-48">{plan.dashboard_title}</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <span className={`text-neutral-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>▾</span>
        </button>

        {isExpanded && (
          <div className="animate-fade-in mx-1 mb-3 px-4 py-3 border border-neutral-200 dark:border-neutral-800 rounded-b bg-neutral-50 dark:bg-neutral-900/50 space-y-3">
            {plan.charts.map(chart => (
              <ChartCard key={chart.chart_id} chart={chart} />
            ))}
          </div>
        )}
      </div>
    )
  }

  if (!isActive) return null

  return (
    <div className="animate-fade-in mt-6">
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/[0.02] dark:bg-amber-400/[0.03] px-6 py-5">
        <StepHeader title="Generate Plan" />
        <p className="font-mono text-xs text-neutral-500 mt-1 mb-5">
          Gemini plans charts based on the inferred semantics.
        </p>

        {errors.plan && (
          <div className="mb-3 font-mono text-xs text-red-400">✕ {errors.plan}</div>
        )}

        <div className="flex items-center gap-4">
          <button
            onClick={generatePlan}
            disabled={isLoading}
            className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-100 dark:disabled:bg-neutral-800 disabled:text-neutral-400 dark:disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer enabled:shadow-sm"
          >
            {isLoading ? 'Planning...' : 'Generate Plan'}
          </button>
          {isLoading && (
            <span className="font-mono text-xs text-neutral-500 animate-pulse">
              Analysing semantics, planning charts...
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

const TYPE_COLOUR = {
  bar:    'text-emerald-400 border-emerald-500/30 bg-emerald-500/5',
  line:   'text-blue-400    border-blue-500/30    bg-blue-500/5',
  scalar: 'text-amber-400   border-amber-500/30   bg-amber-500/5',
  pie:    'text-violet-400  border-violet-500/30  bg-violet-500/5',
}

function ChartCard({ chart }) {
  const typeColour = TYPE_COLOUR[chart.chart_type] ?? 'text-neutral-400 border-neutral-700 bg-neutral-800/20'

  return (
    <div className="border border-neutral-200 dark:border-neutral-800 rounded p-3 hover:border-neutral-300 dark:hover:border-neutral-700 transition-colors duration-150">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="font-mono text-sm text-neutral-900 dark:text-neutral-100 mb-1">
            {chart.chart_title}
          </div>
          <div className="font-mono text-xs text-neutral-500 leading-relaxed">
            {chart.reasoning}
          </div>
        </div>
        <div className={`border rounded px-2 py-1 font-mono text-xs shrink-0 uppercase ${typeColour}`}>
          {chart.chart_type}
        </div>
      </div>
      <div className="mt-2.5 flex gap-4 font-mono text-xs">
        {chart.x_axis && (
          <span className="text-neutral-500">x <span className="text-neutral-600 dark:text-neutral-400">{chart.x_axis}</span></span>
        )}
        {chart.y_axis && (
          <span className="text-neutral-500">y <span className="text-neutral-600 dark:text-neutral-400">{chart.y_axis}</span></span>
        )}
        <span className="text-neutral-500">agg <span className="text-neutral-600 dark:text-neutral-400">{chart.aggregation}</span></span>
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