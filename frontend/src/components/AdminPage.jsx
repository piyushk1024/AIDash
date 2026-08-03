import { useState, useEffect } from 'react'
import { api } from '../lib/api'

function StatCard({ label, value }) {
  return (
    <div className="border border-muted rounded-card bg-surface p-5 flex flex-col gap-1.5">
      <span className="font-mono text-[10.5px] tracking-wide uppercase text-muted">{label}</span>
      <span className="font-display font-semibold text-2xl text-fg">{value}</span>
    </div>
  )
}

export default function AdminPage() {
  const [stats, setStats] = useState(null)
  const [feedback, setFeedback] = useState([])
  const [tab, setTab] = useState('stats')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.getAdminStats(), api.getAdminFeedback()])
      .then(([statsRes, feedbackRes]) => {
        setStats(statsRes)
        setFeedback(feedbackRes)
      })
      .catch(() => setError('Could not load admin data.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="max-w-4xl mx-auto px-8 py-16 font-mono text-xs text-muted animate-pulse">Loading admin data...</div>
  }

  if (error) {
    return <div className="max-w-4xl mx-auto px-8 py-16 font-mono text-xs text-danger">{error}</div>
  }

  return (
    <div className="max-w-4xl mx-auto px-8 py-16">
      <h1 className="font-display font-semibold text-2xl text-fg mb-8">Admin</h1>

      <div className="flex gap-2 mb-8 border-b border-muted">
        {['stats', 'feedback'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 font-display text-xs font-medium uppercase tracking-wide -mb-px border-b-2 transition-colors ${
              tab === t ? 'border-accent text-fg' : 'border-transparent text-muted'
            }`}
          >
            {t === 'stats' ? 'Stats' : 'Feedback'}
          </button>
        ))}
      </div>

      {tab === 'stats' && (
        <div className="grid grid-cols-2 gap-4">
          <StatCard label="Users" value={stats.user_count} />
          <StatCard label="Datasets" value={stats.dataset_count} />
          <StatCard label="Dashboards (Pipeline)" value={stats.dashboards_by_mode.pipeline ?? 0} />
          <StatCard label="Dashboards (Agent)" value={stats.dashboards_by_mode.agent ?? 0} />
          <StatCard label="Feedback Entries" value={stats.feedback_count} />
        </div>
      )}

      {tab === 'feedback' && (
        <div className="flex flex-col gap-2.5">
          {feedback.length === 0 && (
            <p className="font-mono text-xs text-muted">No feedback yet.</p>
          )}
          {feedback.map(f => (
            <div key={f.feedback_id} className="border border-muted rounded-card bg-surface p-4">
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-[10.5px] uppercase tracking-wide text-accent font-semibold">{f.type}</span>
                <span className="font-mono text-[10.5px] text-muted">{new Date(f.created_at).toLocaleString()}</span>
              </div>
              <p className="font-mono text-xs text-fg mb-1.5">{f.message || <span className="text-muted italic">No message</span>}</p>
              <span className="font-mono text-[10.5px] text-muted">{f.username}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}