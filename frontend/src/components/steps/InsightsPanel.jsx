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
    setFetching(true)
    api.getInsights(datasetId)
      .then(res => {
        setHistory(
          (res.insights ?? []).map((entry, i) => ({
            ...entry,
            expanded: i === 0,
            shownCount: 1,
          }))
        )
      })
      .catch(() => {})
      .finally(() => setFetching(false))
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
    } catch (e) {
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
          className="flex-1 bg-transparent border border-neutral-700 rounded px-3 py-2
                     font-mono text-xs text-neutral-200 placeholder-neutral-600
                     focus:outline-none focus:border-amber-400 transition-colors
                     disabled:opacity-50"
        />
        <button
          onClick={handleAsk}
          disabled={loading || !prompt.trim()}
          className="px-4 py-2 rounded font-mono text-xs tracking-widest uppercase transition-all
                     disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed
                     enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300"
        >
          {loading ? '...' : 'Ask →'}
        </button>
      </div>

      {error && (
        <div className="font-mono text-xs text-red-400">✕ {error}</div>
      )}

      {/* History */}
      {fetching ? (
        <div className="font-mono text-xs text-neutral-600 animate-pulse">Loading history...</div>
      ) : history.length > 0 ? (
        <div className="space-y-2 mt-2">
          {history.map((entry, i) => (
            <div key={entry.insight_id} className="border border-neutral-800 rounded overflow-hidden">

              <button
                onClick={() => toggleEntry(i)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-neutral-900 transition-colors"
              >
                <span className="text-amber-400 font-mono text-xs">→</span>
                <span className="font-mono text-xs text-neutral-300 flex-1">{entry.prompt}</span>
                <span
                  onClick={(e) => handleDelete(entry.insight_id, e)}
                  className="font-mono text-[10px] text-neutral-600 hover:text-red-400 transition-colors px-1"
                  title="Delete"
                >
                  ✕
                </span>
                <span className="font-mono text-[10px] text-neutral-600">
                  {entry.expanded ? '▴' : '▾'}
                </span>
              </button>

              {entry.expanded && (
                <div className="px-3 pb-3 space-y-2 border-t border-neutral-800">
                  {entry.insights.slice(0, entry.shownCount).map((insight, j) => (
                    <div key={j} className="pt-2 space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs text-neutral-200">{insight.title}</span>
                        <span className={`font-mono text-[10px] uppercase tracking-wider
                          ${insight.confidence === 'high'   ? 'text-emerald-400' : ''}
                          ${insight.confidence === 'medium' ? 'text-amber-400'   : ''}
                          ${insight.confidence === 'low'    ? 'text-red-400'     : ''}
                        `}>
                          {insight.confidence}
                        </span>
                      </div>
                      <div className="font-mono text-xs text-neutral-500 leading-relaxed">
                        {insight.finding}
                      </div>
                    </div>
                  ))}

                  {entry.shownCount < entry.insights.length && (
                    <button
                      onClick={() => showMore(i)}
                      className="font-mono text-[10px] text-neutral-600 hover:text-amber-400 transition-colors mt-1"
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
        <div className="font-mono text-xs text-neutral-600">No insights yet. Ask a question above.</div>
      )}
    </div>
  )
}