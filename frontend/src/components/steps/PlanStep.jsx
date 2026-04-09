export default function PlanStep({ dasher, isActive, isExpanded, onToggle }) {
  const { generatePlan, status, errors, plan } = dasher

  const isLoading = status.plan === 'loading'
  const isDone    = status.plan === 'done'

  // ── Done — show chart cards ──
if (isDone && plan) {
    return (
      <div className="animate-fade-in">
        <button
          onClick={onToggle}
          className="w-full py-2 flex items-center gap-3 font-mono text-xs hover:opacity-80 transition-opacity text-left"
        >
          <span className="text-neutral-500 uppercase tracking-wider">Generate Plan</span>
          <span className="text-neutral-600">—</span>
          <span className="text-neutral-400">{plan.charts.length} charts</span>
          <span className="text-neutral-600 truncate max-w-48">{plan.dashboard_title}</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <span className={`text-neutral-600 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
            ▾
          </span>
        </button>

        {isExpanded && (
          <div className="animate-fade-in mb-4 space-y-3">
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
    <div className="animate-fade-in mt-12">
      <StepHeader title="Generate Plan" />
      <p className="font-mono text-xs text-neutral-500 mt-2 mb-6">
        Gemini will plan charts based on the inferred semantics.
      </p>

      {errors.plan && (
        <div className="mb-3 font-mono text-xs text-red-400">✕ {errors.plan}</div>
      )}

      <button
        onClick={generatePlan}
        disabled={isLoading}
        className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200
          disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed
          enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
      >
        {isLoading ? 'Planning...' : 'Generate Plan →'}
      </button>

      {isLoading && (
        <div className="mt-3 font-mono text-xs text-neutral-500 animate-pulse">
          Analysing semantics, planning charts...
        </div>
      )}
    </div>
  )
}

// ── Chart type → short label ──────────────────────────────────
const TYPE_LABEL = {
  bar:    'BAR',
  line:   'LINE',
  scalar: 'SCALAR',
  pie:    'PIE',
}

const TYPE_COLOUR = {
  bar:    'text-emerald-400 border-emerald-500/30',
  line:   'text-blue-400    border-blue-500/30',
  scalar: 'text-amber-400   border-amber-500/30',
  pie:    'text-violet-400  border-violet-500/30',
}

function ChartCard({ chart }) {
  const typeColour = TYPE_COLOUR[chart.chart_type] ?? 'text-neutral-400 border-neutral-700'

  return (
    <div className="border border-neutral-800 rounded p-4 hover:border-neutral-600 transition-colors duration-200">
      <div className="flex items-start justify-between gap-4">
        {/* Title + reasoning */}
        <div className="flex-1 min-w-0">
          <div className="font-mono text-sm text-neutral-100 mb-1">
            {chart.chart_title}
          </div>
          <div className="font-mono text-xs text-neutral-500 leading-relaxed">
            {chart.reasoning}
          </div>
        </div>

        {/* Chart type badge */}
        <div className={`border rounded px-2 py-1 font-mono text-xs shrink-0 ${typeColour}`}>
          {TYPE_LABEL[chart.chart_type] ?? chart.chart_type}
        </div>
      </div>

      {/* Axes row */}
      <div className="mt-3 flex gap-4 font-mono text-xs">
        {chart.x_axis && (
          <span className="text-neutral-600">
            x <span className="text-neutral-400">{chart.x_axis}</span>
          </span>
        )}
        {chart.y_axis && (
          <span className="text-neutral-600">
            y <span className="text-neutral-400">{chart.y_axis}</span>
          </span>
        )}
        <span className="text-neutral-600">
          agg <span className="text-neutral-400">{chart.aggregation}</span>
        </span>
      </div>
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