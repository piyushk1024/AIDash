import { useState } from 'react'
import ChartGrid from '../dashboard/ChartGrid'
import InsightsPanel from './InsightsPanel'
import AgentTrace from './AgentTrace'
import HealingSummary from './HealingSummary'
import LaunchCard from './LaunchCard'
import { api } from '../../lib/api'
import { useToast } from '../../hooks/useToast'

const sectionLabel = "font-mono font-semibold text-[10.5px] uppercase tracking-wider text-muted mb-2"

const PIPELINE_STEPS = [
  { key: 'upload', label: 'PROFILE' },
  { key: 'semantics', label: 'SEMANTICS' },
  { key: 'plan', label: 'PLAN' },
  { key: 'dashboard', label: 'BUILD' },
]

const AGENT_STEPS = [
  { key: 'upload', label: 'PROFILE' },
  { key: 'semantics', label: 'SEMANTICS' },
  { key: 'dashboard', label: 'AGENT RUN' },
]

export default function Workspace({ dasher }) {
  const {
    datasetId, uploadResult, status,
    dashboardResult, agentResult, setAgentResult,
    addCard, replaceCard, removeCard, //setDashboardPublished,
    pipelineHint, activeMode,
  } = dasher

  const isAgentMode = activeMode === 'agent'
  const active = isAgentMode ? agentResult : dashboardResult
  const cards = isAgentMode ? (agentResult?.charts_built ?? []) : (dashboardResult?.cards ?? [])
  const fieldMap = uploadResult?.field_map ?? {}
  const published = active?.published ?? false
  const stale = active?.stale ?? false

  const toast = useToast()
  const [activeTab, setActiveTab] = useState('dashboard') // 'dashboard' | 'insights'
  const [showRebuild, setShowRebuild] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [copied, setCopied] = useState(false)  
  
  

  async function handlePublishToggle() {
    setPublishing(true)
    try {
      const mode = isAgentMode ? 'agent' : 'pipeline'
      await api.publishDashboard(datasetId, mode)
      await dasher.rehydrate(datasetId)
    } catch {
      toast.error('Publish failed. Try again.')
      // silently ignore — toggle stays at prior state
    } finally {
      setPublishing(false)
    }
  }

  function handleCopyLink() {
    const url = `${window.location.origin}/share/${datasetId}`
    navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const pipelineSteps = isAgentMode ? AGENT_STEPS : PIPELINE_STEPS
  const datasetLabel = uploadResult?.name || uploadResult?.original_filename || 'Untitled dataset'

  const rebuildContext = {
    name: uploadResult?.name ?? '',
    comment: uploadResult?.comment ?? '',
    pipelineHint: pipelineHint ?? '',
    agentGoal: agentResult?.goal ?? '',
    mode: isAgentMode ? 'agent' : 'pipeline',
  }

  return (
    <div className="max-w-6xl mx-auto px-8 py-10 flex gap-10">
      <aside className="w-64 shrink-0 flex flex-col gap-7">

        <div>
          <div className={sectionLabel}>Active Dataset</div>
          <div className="flex items-center gap-2 mb-2">
            <div className="font-mono text-[13px] text-fg truncate">
              {datasetLabel}
            </div>
            <span className="font-mono text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-icon border border-muted text-muted shrink-0">
              {isAgentMode ? 'Agent' : 'Pipeline'}
            </span>
          </div>
          <div className="font-mono text-[10px] text-muted mb-2">
            {datasetId?.slice(0, 8)}
            </div>
        
          <div className="flex items-center gap-1 p-[3px] border border-muted rounded-control bg-bg w-fit">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`px-3 py-1.5 rounded-icon font-display text-[11px] font-medium uppercase tracking-wide transition-colors ${activeTab === 'dashboard' ? 'bg-accent text-accent-fg font-semibold' : 'text-muted hover:text-fg'}`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setActiveTab('insights')}
              className={`px-3 py-1.5 rounded-icon font-display text-[11px] font-medium uppercase tracking-wide transition-colors ${activeTab === 'insights' ? 'bg-accent text-accent-fg font-semibold' : 'text-muted hover:text-fg'}`}
            >
              Insights
            </button>
          </div>
        </div>

        {activeTab === 'dashboard' && (
          <div>
            <div className={sectionLabel}>Steering Hint</div>
            <button
              onClick={() => setShowRebuild(true)}
              disabled={showRebuild}
              className="w-full px-3 py-2 rounded-control font-display text-[11px] font-semibold uppercase tracking-wide transition-opacity disabled:opacity-40 disabled:cursor-not-allowed enabled:bg-accent enabled:text-accent-fg enabled:cursor-pointer"
            >
              Re-infer Plan
            </button>
          </div>
        )}

        <div>
          <div className={sectionLabel}>Pipeline Status</div>
          <div className="flex flex-col gap-2.5">
            {pipelineSteps.map(step => {
              const done = status[step.key] === 'done'
              const loading = status[step.key] === 'loading'
              return (
                <div key={step.key} className="flex items-center gap-2.5">
                  <div className={`w-[9px] h-[9px] rounded-full shrink-0 ${
                    done ? 'bg-accent border border-accent'
                    : loading ? 'bg-transparent border border-accent'
                    : 'bg-transparent border border-muted'
                  }`} />
                  <span className={`font-mono text-[11.5px] ${done || loading ? 'text-fg font-semibold' : 'text-muted'}`}>
                    {step.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <div>
          <div className={sectionLabel}>Publish</div>
          <button
            onClick={handlePublishToggle}
            disabled={publishing || !active}
            className={`w-full px-3 py-2 rounded-control font-display text-[11px] font-semibold uppercase tracking-wide transition-opacity disabled:opacity-40 disabled:cursor-not-allowed ${
              published
                ? 'border border-accent text-accent'
                : 'bg-accent text-accent-fg'
            }`}
          >
            {publishing ? '…' : published ? 'Published' : 'Private'}
          </button>
          {published && stale && (
            <p className="mt-2 font-mono text-[10.5px] text-danger leading-snug">
              Shared version is out of date — republish to update the public link.
            </p>
          )}
          {published && (
            <button
              onClick={handleCopyLink}
              className="mt-2 w-full font-mono text-[11px] text-muted hover:text-accent transition-colors truncate text-left"
            >
              {copied ? 'Copied!' : `dasher.app/s/${datasetId.slice(0, 8)}`}
            </button>
          )}
        </div>

      </aside>

      <main className="flex-1 min-w-0">
        {activeTab === 'dashboard' ? (
          showRebuild ? (
            <LaunchCard
              dasher={dasher}
              rebuildContext={rebuildContext}
              onDone={() => setShowRebuild(false)}
            />
          ) : (
            <div className="space-y-5">
              {isAgentMode && agentResult?.dashboard_title && (
                <h2 className="font-display font-semibold text-lg text-fg">{agentResult.dashboard_title}</h2>
              )}
              {isAgentMode && agentResult?.rationale && (
                <p className="font-mono text-[12px] text-muted leading-relaxed">{agentResult.rationale}</p>
              )}

              <ChartGrid
                cards={cards}
                datasetId={datasetId}
                fieldMap={fieldMap}
                mode={isAgentMode ? 'agent' : 'pipeline'}
                onCardAdded={card => {
                  if (isAgentMode) {
                    setAgentResult(prev => ({ ...prev, charts_built: [...prev.charts_built, card] }))
                    dasher.rehydrate(datasetId)
                  } else {
                    addCard(card)
                  }
                }}
                onCardEdited={(cardId, card) => {
                  if (isAgentMode) {
                    setAgentResult(prev => ({ ...prev, charts_built: prev.charts_built.map(c => c.card_id === cardId ? card : c) }))
                    dasher.rehydrate(datasetId)
                  } else {
                    replaceCard(cardId, card)
                  }
                }}
                onCardDeleted={cardId => {
                  if (isAgentMode) {
                    setAgentResult(prev => ({ ...prev, charts_built: prev.charts_built.filter(c => c.card_id !== cardId) }))
                    dasher.rehydrate(datasetId)
                  } else {
                    removeCard(cardId)
                  }
                }}

              />

              {isAgentMode && agentResult?.trace?.length > 0 && (
                <AgentTrace trace={agentResult.trace} />
              )}

              {!isAgentMode && (dashboardResult?.cards?.some(c => c.healed) || dashboardResult?.errors?.length > 0) && (
                <HealingSummary cards={dashboardResult.cards} errors={dashboardResult.errors} />
              )}
            </div>
          )
        ) : (
          <InsightsPanel datasetId={datasetId} />
        )}
      </main>
    </div>
  )
}