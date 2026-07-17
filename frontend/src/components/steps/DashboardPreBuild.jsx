import { useState } from 'react'
import AgentTrace from './AgentTrace'
import { StepActiveShell } from '../shared/CollapsibleStep'
import { chartTypeBadgeClass } from '../../lib/chartTypeStyles'
import { useEventStream } from '../../hooks/useEventStream'
import { api } from '../../lib/api'

function toTraceEntries(events) {
  return events
    .filter(e => !['step_started', 'healing', 'rationale', 'finish'].includes(e.type))
    .map(({ type: _, ...rest }) => rest)
}

// Pre-build configuration view for the Build Dashboard step: mode toggle
// (Standard/Agentic), plan preview or goal input depending on mode, and the
// submit button that either runs the pipeline build or streams an agent run.
// Split out of DashboardStep.jsx so DashboardStep can focus purely on
// choosing between this and the two "done" result views.
export default function DashboardPreBuild({ dasher, onDone }) {
  const {
    createDashboard, status, errors, plan, agentResult, dashboardResult,
    applyAgentEvents, datasetId,
  } = dasher

  const [mode, setMode] = useState('pipeline')
  const [goal, setGoal] = useState('')

  const { events, streaming, streamError, startStream, reset } = useEventStream()

  const isLoading = status.dashboard === 'loading'

  async function handleAgentRun() {
    reset()
    const trimmedGoal = goal.trim()
    const result = await startStream(api.agentStreamUrl(datasetId), trimmedGoal ? { goal: trimmedGoal } : {})
    const hasFinish = result.some(e => e.type === 'finish')
    if (hasFinish) {
      applyAgentEvents(result)
      onDone()
    }
  }

  return (
    <StepActiveShell
      title="Build Dashboard"
      description="Runs each chart's query and renders the results directly."
    >
      <div className="flex items-center gap-1 mb-6 p-1 border border-neutral-800 rounded w-fit">
        <button
          onClick={() => setMode('pipeline')}
          className={`px-3 py-1 rounded font-mono text-xs tracking-wider uppercase transition-colors ${mode === 'pipeline' ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-600 hover:text-neutral-400'}`}
        >
          Standard
        </button>
        <button
          onClick={() => setMode('agent')}
          className={`px-3 py-1 rounded font-mono text-xs tracking-wider uppercase transition-colors ${mode === 'agent' ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-600 hover:text-neutral-400'}`}
        >
          Agentic
        </button>
      </div>

      {mode === 'pipeline' && plan && (
        <div className="mb-6 p-4 border border-neutral-800 rounded space-y-2">
          <div className="font-mono text-xs text-neutral-500 uppercase tracking-wider mb-2">Planned</div>
          {plan.charts.map((chart, i) => (
            <div key={chart.chart_title ?? i} className="font-mono text-xs flex items-center gap-3">
              <span className={`border rounded px-1.5 py-0.5 text-[10px] uppercase ${chartTypeBadgeClass(chart.chart_type)}`}>
                {chart.chart_type}
              </span>
              <span className="text-neutral-400">{chart.chart_title}</span>
            </div>
          ))}
        </div>
      )}

      {mode === 'agent' && (
        <div className="mb-6 space-y-2">
          <label className="font-mono text-[10px] text-neutral-600 uppercase tracking-wider">
            Goal <span className="text-neutral-700 normal-case tracking-normal">(optional)</span>
          </label>
          <textarea
            value={goal}
            onChange={e => setGoal(e.target.value)}
            placeholder="e.g. Build a dashboard for C-suite executives focusing on top-line revenue and regional performance"
            rows={3}
            disabled={streaming}
            className="w-full bg-transparent border border-neutral-700 rounded px-3 py-2 font-mono text-xs text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-amber-400 transition-colors resize-none disabled:opacity-50"
          />
          <p className="font-mono text-[10px] text-neutral-700">
            Leave empty to let the agent decide based on the data.
          </p>

          {agentResult && (
            <div className="flex items-center gap-3 p-3 border border-neutral-800 rounded">
              <span className="font-mono text-[10px] text-neutral-500 flex-1">
                Previous agent result cached — {agentResult.charts_built.length} charts
              </span>
              <button
                onClick={onDone}
                className="font-mono text-[10px] text-amber-400 hover:text-amber-300 transition-colors uppercase tracking-wider"
              >
                use previous
              </button>
              <span className="font-mono text-[10px] text-neutral-700">or run again to overwrite</span>
            </div>
          )}
        </div>
      )}

      {mode === 'pipeline' && errors.dashboard && (
        <div className="mb-3 font-mono text-xs text-red-400">✕ {errors.dashboard}</div>
      )}
      {mode === 'agent' && streamError && (
        <div className="mb-3 font-mono text-xs text-red-400">✕ {streamError}</div>
      )}

      {mode === 'pipeline' ? (
        <button
          onClick={() => {
            if (agentResult && !window.confirm('This will replace your Agentic dashboard. Continue?')) return
            createDashboard()
            onDone()
          }}
          disabled={isLoading}
          className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
        >
          {isLoading ? 'Building...' : 'Build Dashboard →'}
        </button>
      ) : (
        <button
          onClick={() => {
            if (dashboardResult && !window.confirm('This will replace your Standard dashboard. Continue?')) return
            handleAgentRun()
          }}
          disabled={streaming}
          className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
        >
          {streaming ? 'Agent running...' : 'Run Agent →'}
        </button>
      )}

      {isLoading && mode === 'pipeline' && (
        <div className="mt-3 font-mono text-xs text-neutral-500 animate-pulse">
          Running chart queries...
        </div>
      )}
      {streaming && toTraceEntries(events).length === 0 && (
        <div className="mt-3 font-mono text-xs text-neutral-500 animate-pulse">
          Agent is starting...
        </div>
      )}
      {streaming && toTraceEntries(events).length > 0 && (
        <div className="mt-4">
          <AgentTrace trace={toTraceEntries(events)} />
        </div>
      )}
    </StepActiveShell>
  )
}