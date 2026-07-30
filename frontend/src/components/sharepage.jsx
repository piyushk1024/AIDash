import { useState, useEffect } from 'react'
import { useParams } from 'react-router'
import Plot from 'react-plotly.js'
import { api } from '../lib/api'

function PublicChartCard({ chart }) {
  if (!chart.spec) {
    return (
      <div className="border border-red-500/30 rounded p-4 font-mono text-xs text-red-400">
        ✕ {chart.chart_title ?? 'Untitled chart'} — could not be built
      </div>
    )
  }

  const rowCount = chart.rows?.length ?? 0
  const chartHeight = chart.chart_type === 'row'
    ? Math.max(320, rowCount * 28 + 100)
    : 320

  return (
    <div className="border border-neutral-800 rounded p-2">
      <Plot
        data={chart.spec.data ?? []}
        layout={{ autosize: true,
          margin: { t: 32, r: 16, b: 60, l: 60 },
          xaxis: { automargin: true, ...chart.spec.layout?.xaxis },
          yaxis: { automargin: true, ...chart.spec.layout?.yaxis },
          ...chart.spec.layout }}
        useResizeHandler
        style={{ width: '100%', height: `${chartHeight}px` }}
        config={{ displayModeBar: false, responsive: true }}
      />
    </div>
  )
}

export default function SharePage() {
  const { datasetId } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getPublicDashboard(datasetId)
      .then(res => setData(res))
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

        {!error && !data && (
          <div className="font-mono text-xs text-neutral-600 animate-pulse">
            Loading dashboard...
          </div>
        )}

        {data && (
          <>
            {data.dashboard_title && (
              <h1 className="font-mono text-lg text-neutral-200 mb-2">
                {data.dashboard_title}
              </h1>
            )}

            {data.rationale && (
              <div className="border border-amber-400/20 rounded p-4 mb-6 font-mono text-xs text-neutral-400 leading-relaxed">
                {data.rationale}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:grid-flow-row-dense">
              {(data.charts ?? []).map((chart, i) => (
                <div
                  key={chart.chart_title ?? i}
                  className={chart.chart_type === 'row' ? 'md:col-span-2' : ''}
                >
                  <PublicChartCard chart={chart} />
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}