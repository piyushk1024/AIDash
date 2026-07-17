import { StepDoneRow, StepActiveShell } from '../shared/CollapsibleStep'
import { chartTypeBadgeClass } from '../../lib/chartTypeStyles'

// Renamed from the previous local "ChartCard" to avoid colliding with
// DashboardStep/ChartGrid's ChartCard, which renders an actual built chart —
// this one only previews a planned chart's title + reasoning, pre-build.
function PlannedChartCard({ chart }) {
  return (
    <div className={`border rounded p-3 hover:border-neutral-300 dark:hover:border-neutral-700 transition-colors duration-150 ${chartTypeBadgeClass(chart.chart_type)}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="font-mono text-sm text-neutral-900 dark:text-neutral-100 mb-1">
            {chart.chart_title}
          </div>
          <div className="font-mono text-xs text-neutral-500 leading-relaxed">
            {chart.reasoning}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function PlanStep({ dasher, isActive, isExpanded, onToggle }) {
  const { generatePlan, status, errors, plan } = dasher

  const isLoading = status.plan === 'loading'
  const isDone    = status.plan === 'done'

  if (isDone && plan) {
    return (
      <StepDoneRow
        label="Plan"
        summary={
          <>
            <span className="text-neutral-700 dark:text-neutral-300">{plan.charts.length} charts</span>
            <span className="text-neutral-400 truncate max-w-48">{plan.dashboard_title}</span>
          </>
        }
        isExpanded={isExpanded}
        onToggle={onToggle}
      >
        <div className="space-y-3">
          {plan.charts.map((chart, i) => (
            <PlannedChartCard key={chart.chart_title ?? i} chart={chart} />
          ))}
        </div>
      </StepDoneRow>
    )
  }

  if (!isActive) return null

  return (
    <StepActiveShell
      title="Generate Plan"
      description="The LLM plans charts based on the inferred semantics."
    >
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
    </StepActiveShell>
  )
}