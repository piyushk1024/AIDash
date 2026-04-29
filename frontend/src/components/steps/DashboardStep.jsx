import { useState } from 'react'
import InsightsPanel from './InsightsPanel'

export default function DashboardStep({ dasher, isActive, isExpanded, onToggle }) {
  const { createDashboard, status, errors, dashboardResult, plan, datasetId } = dasher
  const [activeTab, setActiveTab] = useState('dashboard')
  const isLoading = status.dashboard === 'loading'
  const isDone = status.dashboard === 'done'

  if (isDone && dashboardResult) {
    return (
      <div className="animate-fade-in mt-6">
        <div className="w-full py-2 flex items-center gap-3 font-mono text-xs text-left">
          <span className="text-neutral-500 uppercase tracking-wider">Build Dashboard</span>
          <span className="text-neutral-600">—</span>
          <span className="text-neutral-400">{dashboardResult.cards_created} cards created</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <button
            onClick={createDashboard}
            disabled={isLoading}
            className="font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors"
          >
            {isLoading ? '...' : '[ rebuild ]'}
          </button>
        </div>

        <div className="flex gap-0 border-b border-neutral-200 dark:border-neutral-800 mt-2">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`px-4 py-2 font-mono text-xs uppercase tracking-wider transition-colors ${activeTab === 'dashboard' ? 'text-amber-400 border-b-2 border-amber-400 -mb-px' : 'text-neutral-500 hover:text-neutral-300'}`}
          >
            dashboard
          </button>
          <button
            onClick={() => setActiveTab('insights')}
            className={`px-4 py-2 font-mono text-xs uppercase tracking-wider transition-colors ${activeTab === 'insights' ? 'text-amber-400 border-b-2 border-amber-400 -mb-px' : 'text-neutral-500 hover:text-neutral-300'}`}
          >
            insights
          </button>
        </div>

        <div className={activeTab === 'dashboard' ? 'block' : 'hidden'}>
          <div className="mt-4 space-y-4">
            <button
              onClick={() => window.open(dashboardResult.dashboard_url, '_blank')}
              className="inline-flex items-center gap-2 px-4 py-2 border border-amber-400/40 rounded font-mono text-xs text-amber-400 hover:bg-amber-400/10 transition-colors"
            >
              Open in Metabase ↗
            </button>
            <iframe
              src={dashboardResult.public_url}
              title="Metabase Dashboard"
              className="w-full rounded border border-neutral-800"
              style={{ height: '520px' }}
            />
          </div>
        </div>

        <div className={activeTab === 'insights' ? 'block' : 'hidden'}>
          <div className="mt-4">
            <InsightsPanel datasetId={datasetId} />
          </div>
        </div>
      </div>
    )
  }

  if (!isActive) return null

  return (
    <div className="animate-fade-in mt-12">
      <StepHeader title="Build Dashboard" />
      <p className="font-mono text-xs text-neutral-500 mt-2 mb-6">
        Creates the dashboard and all chart cards in Metabase via API.
      </p>

      {plan && (
        <div className="mb-6 p-4 border border-neutral-800 rounded space-y-2">
          <div className="font-mono text-xs text-neutral-500 uppercase tracking-wider mb-2">
            Planned
          </div>
          {plan.charts.map(chart => (
            <div key={chart.chart_id} className="font-mono text-xs flex items-center gap-3">
              <span className={`border rounded px-1.5 py-0.5 text-[10px] uppercase ${chart.chart_type === 'bar' ? 'border-emerald-500/30 text-emerald-400' : chart.chart_type === 'line' ? 'border-blue-500/30 text-blue-400' : chart.chart_type === 'scalar' ? 'border-amber-500/30 text-amber-400' : 'border-violet-500/30 text-violet-400'}`}>
                {chart.chart_type}
              </span>
              <span className="text-neutral-400">{chart.chart_title}</span>
            </div>
          ))}
        </div>
      )}

      {errors.dashboard && (
        <div className="mb-3 font-mono text-xs text-red-400">✕ {errors.dashboard}</div>
      )}

      <button
        onClick={createDashboard}
        disabled={isLoading}
        className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
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

function StepHeader({ title }) {
  return (
    <div className="flex items-center gap-3 mb-2">
      <h2 className="font-mono text-sm tracking-widest uppercase text-neutral-900 dark:text-neutral-100">
        {title}
      </h2>
    </div>
  )
}