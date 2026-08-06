import { useState, useEffect } from 'react'
import { api } from '../../lib/api'

export default function InsightsPanel({ datasetId }) {
  const [prompt, setPrompt]   = useState('')
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [error, setError]     = useState(null)
  const [history, setHistory] = useState([]) // { insight_id, prompt, insights, expanded, shownCount }

  useEffect(() => {
    if (!datasetId) return
    let cancelled = false
    // setFetching(true)
    api.getInsights(datasetId)
      .then(res => {
         if (cancelled) return
        setHistory(
          (res.insights ?? []).map((entry, i) => ({
            ...entry,
            expanded: i === 0,
            shownCount: 1,
          }))
        )
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setFetching(false) })
      return () => {cancelled = true}
  }, [datasetId])

  async function handleAsk() {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.askInsight(datasetId, prompt.trim())
      setHistory(prev => [{
        insight_id: result.insight_id,
        prompt: result.prompt,
        insights: result.insights,
        expanded: true,
        shownCount: 1,
      }, ...prev.map(e => ({ ...e, expanded: false }))])
      setPrompt('')
    } catch {
      setError('Something went wrong. Try again.')
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAsk()
    }
  }

  function toggleEntry(i) {
    setHistory(prev => prev.map((e, idx) =>
      idx === i ? { ...e, expanded: !e.expanded } : e
    ))
  }

  function showMore(i) {
    setHistory(prev => prev.map((e, idx) =>
      idx === i ? { ...e, shownCount: e.insights.length } : e
    ))
  }

  async function handleDelete(insightId, e) {
    e.stopPropagation()
    try {
      await api.deleteInsight(datasetId, insightId)
      setHistory(prev => prev.filter(entry => entry.insight_id !== insightId))
    } catch {
      // silently ignore — entry stays in list
    }
  }

  return (
    <div className="space-y-4">
      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. Which team wins most often?"
          disabled={loading}
          className="flex-1 bg-transparent border border-muted rounded px-3 py-2
                     font-mono text-xs text-fg placeholder-muted
                     focus:outline-none focus:border-accent transition-colors
                     disabled:opacity-50"
        />
        <button
          onClick={handleAsk}
          disabled={loading || !prompt.trim()}
          className="px-4 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all
                     disabled:bg-surface disabled:text-muted disabled:cursor-not-allowed
                     enabled:bg-accent enabled:text-accent-fg enabled:hover:bg-accent/90"
        >
          {loading ? '...' : 'Ask →'}
        </button>
      </div>
      <p className="font-mono text-[10px] text-muted leading-relaxed">
        Insights are AI-generated and may be inaccurate. Verify against source data for important decisions. Early stage feature.
      </p>

      {error && (
        <div className="font-mono text-xs text-red-400">✕ {error}</div>
      )}

      {/* History */}
      {fetching ? (
        <div className="font-mono text-xs text-muted animate-pulse">Loading history...</div>
      ) : history.length > 0 ? (
        <div className="space-y-2 mt-2">
          {history.map((entry, i) => (
            <div key={entry.insight_id} className="border border-muted/40 rounded overflow-hidden">

              <button
                onClick={() => toggleEntry(i)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface transition-colors"
              >
                <span className="text-accent font-mono text-xs">→</span>
                <span className="font-mono text-xs text-fg flex-1">{entry.prompt}</span>
                <span
                  onClick={(e) => handleDelete(entry.insight_id, e)}
                  className="font-mono text-[15px] text-muted hover:text-red-400 transition-colors px-1"
                  title="Delete"
                >
                  🗑
                </span>
                <span className="font-mono text-[10px] text-muted">
                  {entry.expanded ? '▴' : '▾'}
                </span>
              </button>

              {entry.expanded && (
                <div className="px-3 pb-3 space-y-2 border-t border-muted/40">
                  {entry.insights.slice(0, entry.shownCount).map((insight, j) => (
                    <div key={j} className="pt-2 space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs text-fg">{insight.title}</span>
                        <span className={`font-mono text-[10px] uppercase tracking-wider
                          ${insight.confidence === 'high'   ? 'text-emerald-400' : ''}
                          ${insight.confidence === 'medium' ? 'text-amber-400'   : ''}
                          ${insight.confidence === 'low'    ? 'text-red-400'     : ''}
                        `}>
                          {insight.confidence}
                        </span>
                      </div>
                      <div className="font-mono text-xs text-muted leading-relaxed">
                        {insight.finding}
                      </div>
                    </div>
                  ))}

                  {entry.shownCount < entry.insights.length && (
                    <button
                      onClick={() => showMore(i)}
                      className="font-mono text-[10px] text-muted hover:text-accent transition-colors mt-1"
                    >
                      + {entry.insights.length - entry.shownCount} more
                    </button>
                  )}
                </div>
              )}

            </div>
          ))}
        </div>
      ) : (
        <div className="font-mono text-xs text-muted">No insights yet. Ask a question above.</div>
      )}
    </div>
  )
}