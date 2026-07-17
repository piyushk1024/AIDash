import { useState, useEffect } from 'react'
import InsightsPanel from './InsightsPanel'
import AgentTrace from './AgentTrace'
import HealingSummary from './HealingSummary'
import PublishBar from './PublishBar'
import DashboardPreBuild from './DashboardPreBuild'
import ChartGrid from '../dashboard/ChartGrid'
import { api } from '../../lib/api'

export default function DashboardStep({ dasher, isActive }) {
  const {
    status, dashboardResult, datasetId, uploadResult,
    addCard, replaceCard, removeCard, setDashboardPublished,
    agentResult, setAgentResult,
  } = dasher

  const [activeTab, setActiveTab] = useState('dashboard')
  const [publishing, setPublishing] = useState(false)
  const [published, setPublished] = useState(dashboardResult?.published ?? false)
  const [copyLabel, setCopyLabel] = useState('Copy share link')
  const [showPreBuild, setShowPreBuild] = useState(false)

  const isDone = status.dashboard === 'done'
  const fieldMap = uploadResult?.field_map ?? {}

  // Sync published from whichever result is active — covers rehydration case
  // where agentResult/dashboardResult arrive after component has mounted.
  useEffect(() => {
    const active = agentResult ?? dashboardResult
    if (active?.published !== undefined) setPublished(active.published)
  }, [agentResult, dashboardResult])

  async function handlePublishToggle(publishMode) {
    setPublishing(true)
    try {
      const result = await api.publishDashboard(datasetId, publishMode)
      setPublished(result.published)
      if (publishMode === 'agent') {
        setAgentResult(prev => ({ ...prev, published: result.published }))
      } else {
        setDashboardPublished(result.published)
      }
    } catch {
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

        <PublishBar
          published={published}
          publishing={publishing}
          onPublish={() => handlePublishToggle('agent')}
          copyLabel={copyLabel}
          onCopy={handleCopyLink}
        />

        <div className="flex gap-0 border-b border-neutral-800 mt-2">
          {tabs('dashboard', 'agent-trace', 'insights')}
        </div>

        <div className={activeTab === 'dashboard' ? 'block mt-4 space-y-4' : 'hidden'}>
          {agentResult.dashboard_title && (
            <h3 className="font-mono text-sm text-neutral-200">{agentResult.dashboard_title}</h3>
          )}
          {agentResult.rationale && (
            <p className="font-mono text-xs text-neutral-500 leading-relaxed">{agentResult.rationale}</p>
          )}
          <ChartGrid
            cards={agentResult.charts_built}
            datasetId={datasetId}
            fieldMap={fieldMap}
            mode="agent"
            onCardAdded={card => setAgentResult(prev => ({ ...prev, charts_built: [...prev.charts_built, card] }))}
            onCardEdited={(cardId, card) => setAgentResult(prev => ({
              ...prev,
              charts_built: prev.charts_built.map(c => c.card_id === cardId ? card : c),
            }))}
            onCardDeleted={cardId => setAgentResult(prev => ({
              ...prev,
              charts_built: prev.charts_built.filter(c => c.card_id !== cardId),
            }))}
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
            disabled={status.dashboard === 'loading'}
            className="font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors"
          >
            {status.dashboard === 'loading' ? '...' : '[ rebuild ]'}
          </button>
        </div>

        <PublishBar
          published={published}
          publishing={publishing}
          onPublish={() => handlePublishToggle('pipeline')}
          copyLabel={copyLabel}
          onCopy={handleCopyLink}
        />

        <div className="flex gap-0 border-b border-neutral-800 mt-2">
          {tabs('dashboard', 'insights')}
        </div>

        <div className={activeTab === 'dashboard' ? 'block mt-4 space-y-4' : 'hidden'}>
          <ChartGrid
            cards={dashboardResult.cards}
            datasetId={datasetId}
            fieldMap={fieldMap}
            mode="pipeline"
            onCardAdded={card => addCard(card)}
            onCardEdited={(cardId, card) => replaceCard(cardId, card)}
            onCardDeleted={cardId => removeCard(cardId)}
          />
          {(dashboardResult.cards?.some(c => c.healed) || dashboardResult.errors?.length > 0) && (
            <HealingSummary cards={dashboardResult.cards} errors={dashboardResult.errors} />
          )}
        </div>

        <div className={activeTab === 'insights' ? 'block mt-4' : 'hidden'}>
          <InsightsPanel datasetId={datasetId} />
        </div>
      </div>
    )
  }

  if (!isActive && !showPreBuild) return null

  return <DashboardPreBuild dasher={dasher} onDone={() => setShowPreBuild(false)} />
}