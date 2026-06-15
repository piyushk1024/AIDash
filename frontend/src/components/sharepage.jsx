import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'

export default function SharePage() {
  const { datasetId } = useParams()
  const [publicUrl, setPublicUrl] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getPublicDashboard(datasetId)
      .then(res => setPublicUrl(res.public_url))
      .catch(() => setError('This dashboard is not available.'))
  }, [datasetId])

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800 px-8 py-4 flex items-center gap-3">
        <div className="w-5 h-5 bg-amber-400 rounded-sm rotate-45 shrink-0" />
        <span className="font-mono text-sm tracking-widest uppercase text-neutral-400">
          Dasher
        </span>
      </header>

      <div className="max-w-5xl mx-auto px-8 py-10">
        {error && (
          <div className="font-mono text-sm text-neutral-500">{error}</div>
        )}

        {!error && !publicUrl && (
          <div className="font-mono text-xs text-neutral-600 animate-pulse">
            Loading dashboard...
          </div>
        )}

        {publicUrl && (
          <iframe
            src={`${publicUrl}#hide_download_button=true`}
            title="Dasher Dashboard"
            className="w-full rounded border border-neutral-800"
            style={{ height: '80vh' }}
          />
        )}
      </div>
    </div>
  )
}