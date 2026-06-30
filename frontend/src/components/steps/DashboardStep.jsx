import { useState, useEffect } from 'react'
import InsightsPanel from './InsightsPanel'
import AgentTrace from './AgentTrace'
import HealingSummary from './HealingSummary'
import PublishBar from './PublishBar'
import NLAuthoringPanel from './NLAuthoringPanel'
import { useEventStream } from '../../hooks/useEventStream'
import { api } from '../../lib/api'

function toTraceEntries(events) {
  return events
    .filter(e => e.type !== 'step_started' && e.type !== 'healing')
    .map(({ type, charts_built, dashboard_id, public_url, ...rest }) => rest)
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

export default function DashboardStep({ dasher, isActive }) {
  const {
    createDashboard, status, errors, dashboardResult, plan, datasetId,
    uploadResult, addCard, replaceCard, removeCard, setDashboardPublished, agentResult, setAgentResult
  } = dasher

  const [activeTab, setActiveTab] = useState('dashboard')
  const [iframeKey, setIframeKey] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [published, setPublished] = useState(dashboardResult?.published ?? false)
  const [copyLabel, setCopyLabel] = useState('Copy share link')

  const [showPreBuild, setShowPreBuild] = useState(false)

  const [mode, setMode] = useState('pipeline')
  const [goal, setGoal] = useState('')

  const { events, streaming, streamError, startStream, reset } = useEventStream()


  const isLoading = status.dashboard === 'loading'
  const isDone = status.dashboard === 'done'
  const fieldMap = uploadResult?.field_map ?? {}

  // Sync published from whichever result is active — covers rehydration case
  // where agentResult/dashboardResult arrive after component has mounted.
  useEffect(() => {
    const active = agentResult ?? dashboardResult
    if (active?.published !== undefined) setPublished(active.published)
  }, [agentResult, dashboardResult])

  function bumpIframe() { setIframeKey(k => !k) }

  async function handlePublishToggle() {
    setPublishing(true)
    try {
      const result = await api.publishDashboard(datasetId)
      setPublished(result.published)
      if (agentResult) {
      setAgentResult(prev => ({ ...prev, published: result.published }))
      } else {
        setDashboardPublished(result.published)
      }
      setDashboardPublished(result.published)
    } catch (e) {
      // silently ignore — button reverts to prior state
    } finally {
      setPublishing(false)
    }
  }

  function handleCopyLink() {
    const url = `${window.location.origin}/share/${datasetId}`
    navigator.clipboard.writeText(url)
    setCopyLabel('Copied!')
    setTimeout(() => setCopyLabel('Copy share link'), 2000)
  }

  async function handleAgentRun() {
  reset()
  // const result = await startStream(api.agentStreamUrl(datasetId), { goal: goal.trim() || null })
  const trimmedGoal = goal.trim()
  const result = await startStream(api.agentStreamUrl(datasetId), trimmedGoal ? { goal: trimmedGoal } : {})
  const finishEvent = result.find(e => e.type === 'finish')
  if (finishEvent) {
    setAgentResult({
      charts_built: finishEvent.charts_built,
      trace: toTraceEntries(result),
      public_url: finishEvent.public_url,
      dashboard_id: finishEvent.dashboard_id,
      published: false,
    })
    setShowPreBuild(false)
  }
  }

  const publishBarProps = { published, publishing, onPublish: handlePublishToggle, copyLabel, onCopy: handleCopyLink }

  const tabs = (...names) => names.map(name => (
    <button
      key={name}
      onClick={() => setActiveTab(name)}
      className={`px-4 py-2 font-mono text-xs uppercase tracking-wider transition-colors ${activeTab === name ? 'text-amber-400 border-b-2 border-amber-400 -mb-px' : 'text-neutral-500 hover:text-neutral-300'}`}
    >
      {name.replace('-', ' ')}
    </button>
  ))

  // Agent done view
  if (agentResult && !showPreBuild) {
    return (
      <div className="animate-fade-in mt-6">
        <div className="w-full py-2 flex items-center gap-3 font-mono text-xs">
          <span className="text-neutral-500 uppercase tracking-wider">Build Dashboard</span>
          <span className="text-neutral-600">—</span>
          <span className="text-neutral-400">{agentResult.charts_built.length} charts built</span>
          <span className="text-neutral-600 ml-1">· agent</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <button
            onClick={() => { setShowPreBuild(true); setActiveTab('dashboard') }}
            className="font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors"
          >
            [ rebuild ]
          </button>
        </div>

        <PublishBar {...publishBarProps} />

        <div className="flex gap-0 border-b border-neutral-800 mt-2">
          {tabs('dashboard', 'agent-trace', 'insights')}
        </div>

        <div className={activeTab === 'dashboard' ? 'block mt-4 space-y-4' : 'hidden'}>
          <button
            onClick={() => window.open(agentResult.public_url, '_blank')}
            className="inline-flex items-center gap-2 px-4 py-2 border border-amber-400/40 rounded font-mono text-xs text-amber-400 hover:bg-amber-400/10 transition-colors"
          >
            Open in Metabase ↗
          </button>
          <iframe
            key={iframeKey}
            src={agentResult.public_url}
            title="Metabase Dashboard"
            className="w-full rounded border border-neutral-800"
            style={{ height: '520px' }}
          />
        </div>

        <div className={activeTab === 'agent-trace' ? 'block mt-4' : 'hidden'}>
          <AgentTrace trace={agentResult.trace} />
        </div>

        <div className={activeTab === 'insights' ? 'block mt-4' : 'hidden'}>
          <InsightsPanel datasetId={datasetId} />
        </div>
      </div>
    )
  }

  // Pipeline done view
  if (!showPreBuild && isDone && dashboardResult) {
    return (
      <div className="animate-fade-in mt-6">
        <div className="w-full py-2 flex items-center gap-3 font-mono text-xs">
          <span className="text-neutral-500 uppercase tracking-wider">Build Dashboard</span>
          <span className="text-neutral-600">—</span>
          <span className="text-neutral-400">{dashboardResult.cards_created} cards created</span>
          <span className="text-amber-400 ml-auto">✓</span>
          <button
            onClick={() => { setShowPreBuild(true); setActiveTab('dashboard') }}
            disabled={isLoading}
            className="font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors"
          >
            {isLoading ? '...' : '[ rebuild ]'}
          </button>
        </div>

        <PublishBar {...publishBarProps} />

        <div className="flex gap-0 border-b border-neutral-800 mt-2">
          {tabs('dashboard', 'insights')}
        </div>

        <div className={activeTab === 'dashboard' ? 'block mt-4 space-y-4' : 'hidden'}>
          <button
            onClick={() => window.open(dashboardResult.dashboard_url, '_blank')}
            className="inline-flex items-center gap-2 px-4 py-2 border border-amber-400/40 rounded font-mono text-xs text-amber-400 hover:bg-amber-400/10 transition-colors"
          >
            Open in Metabase ↗
          </button>
          <iframe
            key={iframeKey}
            src={dashboardResult.public_url}
            title="Metabase Dashboard"
            className="w-full rounded border border-neutral-800"
            style={{ height: '520px' }}
          />
          {(dashboardResult.cards?.some(c => c.healed) || dashboardResult.errors?.length > 0) && (
            <HealingSummary cards={dashboardResult.cards} errors={dashboardResult.errors} />
          )}
          <NLAuthoringPanel
            datasetId={datasetId}
            fieldMap={fieldMap}
            cards={dashboardResult.cards ?? []}
            onCardAdded={card => { addCard(card); bumpIframe() }}
            onCardEdited={(cardId, card) => { replaceCard(cardId, card); bumpIframe() }}
            onCardDeleted={cardId => { removeCard(cardId); bumpIframe() }}
          />
        </div>

        <div className={activeTab === 'insights' ? 'block mt-4' : 'hidden'}>
          <InsightsPanel datasetId={datasetId} />
        </div>
      </div>
    )
  }

  if (!isActive && !showPreBuild) return null

  // Pre-build view
  return (
    <div className="animate-fade-in mt-12">
      <StepHeader title="Build Dashboard" />
      <p className="font-mono text-xs text-neutral-500 mt-2 mb-6">
        Creates the dashboard and all chart cards in Metabase via API.
      </p>

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
              onClick={() => setShowPreBuild(false)}
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
      {mode === 'agent' && streamError  && (
        <div className="mb-3 font-mono text-xs text-red-400">✕ {streamError}</div>
      )}

      {mode === 'pipeline' ? (
        <button
          onClick={() => { setShowPreBuild(false); createDashboard() }}
          disabled={isLoading}
          className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
        >
          {isLoading ? 'Building...' : 'Build Dashboard →'}
        </button>
      ) : (
        <button
          onClick={handleAgentRun}
          disabled={streaming}
          className="px-6 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
        >
          {streaming ? 'Agent running...' : 'Run Agent →'}
        </button>
      )}

      {isLoading && mode === 'pipeline' && (
        <div className="mt-3 font-mono text-xs text-neutral-500 animate-pulse">
          Creating cards in Metabase...
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
    </div>
  )
}