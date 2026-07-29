import { useState } from 'react'
import ChartGrid from '../dashboard/ChartGrid'
import InsightsPanel from './InsightsPanel'
import AgentTrace from './AgentTrace'
import HealingSummary from './HealingSummary'
import { api } from '../../lib/api'

const sectionLabel = "font-mono font-semibold text-[10.5px] uppercase tracking-wider text-muted mb-2"

export default function Workspace({ dasher }) {
  const {
    datasetId, uploadResult, status,
    dashboardResult, agentResult, setAgentResult,
    addCard, replaceCard, removeCard, setDashboardPublished,
    inferSemantics, generatePlan, createDashboard,
  } = dasher

  const isAgentMode = Boolean(agentResult)
  const active = agentResult ?? dashboardResult
  const cards = isAgentMode ? agentResult.charts_built : (dashboardResult?.cards ?? [])
  const fieldMap = uploadResult?.field_map ?? {}
  const published = active?.published ?? false

  const [activeTab, setActiveTab] = useState('dashboard') // 'dashboard' | 'insights'
  const [hint, setHint] = useState('')
  const [reinferring, setReinferring] = useState(false)
  const [reinferError, setReinferError] = useState(null)
  const [publishing, setPublishing] = useState(false)
  const [copied, setCopied] = useState(false)

  async function handleReinfer() {
    if (isAgentMode) return // agent-mode re-infer not wired to any route yet
    setReinferring(true)
    setReinferError(null)
    try {
      await inferSemantics(hint.trim() || null, true)
      await generatePlan()
      await createDashboard()
    } catch (e) {
      setReinferError(e.message)
    } finally {
      setReinferring(false)
    }
  }

  async function handlePublishToggle() {
    setPublishing(true)
    try {
      const mode = isAgentMode ? 'agent' : 'pipeline'
      const result = await api.publishDashboard(datasetId, mode)
      if (isAgentMode) {
        setAgentResult(prev => ({ ...prev, published: result.published }))
      } else {
        setDashboardPublished(result.published)
      }
    } catch {
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

  const pipelineSteps = [
    { key: 'upload', label: 'PROFILE' },
    { key: 'semantics', label: 'SEMANTICS' },
    { key: 'plan', label: 'PLAN' },
    { key: 'dashboard', label: 'BUILD' },
  ]

  return (
    <div className="max-w-6xl mx-auto px-8 py-10 flex gap-10">
      <aside className="w-64 shrink-0 flex flex-col gap-7">

        <div>
          <div className={sectionLabel}>Active Dataset</div>
          <div className="font-mono text-[13px] text-fg truncate mb-2">
            {uploadResult?.name || uploadResult?.original_filename || 'Untitled dataset'}
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

        <div>
          <div className={sectionLabel}>Steering Hint</div>
          <textarea
            value={hint}
            onChange={e => setHint(e.target.value)}
            placeholder="e.g. focus on regional revenue trends and flag anomalies"
            rows={3}
            disabled={isAgentMode}
            className="w-full bg-bg border border-muted rounded-control px-2.5 py-2 font-mono text-[11.5px] text-fg placeholder-muted/60 focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-50"
          />
          <button
            onClick={handleReinfer}
            disabled={reinferring || isAgentMode}
            title={isAgentMode ? 'Re-infer not available in agent mode yet' : undefined}
            className="mt-2 w-full px-3 py-2 rounded-control font-display text-[11px] font-semibold uppercase tracking-wide transition-opacity disabled:opacity-40 disabled:cursor-not-allowed enabled:bg-accent enabled:text-accent-fg enabled:cursor-pointer"
          >
            {reinferring ? 'Re-inferring…' : 'Re-infer Plan'}
          </button>
          {reinferError && (
            <div className="mt-1.5 font-mono text-[11px] text-danger">✕ {reinferError}</div>
          )}
        </div>

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
          <div className="space-y-5">
            {isAgentMode && agentResult.dashboard_title && (
              <h2 className="font-display font-semibold text-lg text-fg">{agentResult.dashboard_title}</h2>
            )}
            {isAgentMode && agentResult.rationale && (
              <p className="font-mono text-[12px] text-muted leading-relaxed">{agentResult.rationale}</p>
            )}

            <ChartGrid
              cards={cards}
              datasetId={datasetId}
              fieldMap={fieldMap}
              mode={isAgentMode ? 'agent' : 'pipeline'}
              onCardAdded={card => isAgentMode
                ? setAgentResult(prev => ({ ...prev, charts_built: [...prev.charts_built, card] }))
                : addCard(card)}
              onCardEdited={(cardId, card) => isAgentMode
                ? setAgentResult(prev => ({ ...prev, charts_built: prev.charts_built.map(c => c.card_id === cardId ? card : c) }))
                : replaceCard(cardId, card)}
              onCardDeleted={cardId => isAgentMode
                ? setAgentResult(prev => ({ ...prev, charts_built: prev.charts_built.filter(c => c.card_id !== cardId) }))
                : removeCard(cardId)}
            />

            {isAgentMode && agentResult.trace?.length > 0 && (
              <AgentTrace trace={agentResult.trace} />
            )}

            {!isAgentMode && (dashboardResult?.cards?.some(c => c.healed) || dashboardResult?.errors?.length > 0) && (
              <HealingSummary cards={dashboardResult.cards} errors={dashboardResult.errors} />
            )}
          </div>
        ) : (
          <InsightsPanel datasetId={datasetId} />
        )}
      </main>
    </div>
  )
}