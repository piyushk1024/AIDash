import { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router'
import Plot from 'react-plotly.js'
import Plotly from 'plotly.js/dist/plotly'
import { api } from '../lib/api'
import { useTheme } from '../hooks/useTheme'
import Modal from './Modal'
import Footer from './Footer'

function timeAgo(iso) {
  if (!iso) return null
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

// Toolbar is view-only: autoscale + expand + save-image. No edit/delete —
// public viewers have no auth/ownership, those actions don't apply here.
function PublicChartCard({ chart }) {
  const localGdRef = useRef(null)
  const modalGdRef = useRef(null)
  const [expanded, setExpanded] = useState(false)

  function handleAutoscale() {
    const gd = localGdRef.current
    if (!gd) return
    Plotly.relayout(gd, { 'xaxis.autorange': true, 'yaxis.autorange': true })
  }

  function handleModalAutoscale() {
    const gd = modalGdRef.current
    if (!gd) return
    Plotly.relayout(gd, { 'xaxis.autorange': true, 'yaxis.autorange': true })
  }

  async function handleSaveImage() {
    const gd = modalGdRef.current
    if (!gd) return
    try {
      const dataUrl = await Plotly.toImage(gd, {
        format: 'png',
        width: gd._fullLayout?.width,
        height: gd._fullLayout?.height,
        scale: 3,
      })
      const a = document.createElement('a')
      a.href = dataUrl
      a.download = `${chart.chart_title || 'chart'}.png`
      a.click()
    } catch {
      // silently skip if not rendered yet
    }
  }

  if (!chart.spec) {
    return (
      <div className="border border-danger/30 rounded-card p-4 font-mono text-xs text-danger">
        ✕ {chart.chart_title ?? 'Untitled chart'} — could not be built
      </div>
    )
  }

  const chartHeight =  320

  const plotLayout = {
    autosize: true,
    margin: { t: 32, r: 16, b: 60, l: 60 },
    xaxis: { automargin: true, ...chart.spec.layout?.xaxis },
    yaxis: { automargin: true, ...chart.spec.layout?.yaxis },    
  }

  return (
    <div className="border border-muted rounded-card bg-surface overflow-hidden relative group">
      <div className="px-4 py-3.5 border-b border-muted flex items-center justify-between">
        <span className="font-display font-medium text-[13.5px] text-fg">
          {chart.chart_title}
        </span>
        <div className="hidden group-hover:flex gap-3">
          <button onClick={handleAutoscale} title="Autoscale" className="bg-transparent text-muted hover:text-accent text-base">
            ⟳
          </button>
          <button onClick={() => setExpanded(true)} title="Expand" className="bg-transparent text-muted hover:text-accent text-base">
            ⤢
          </button>
        </div>
      </div>
      <div className="p-2">
        <Plot
          ref={el => { localGdRef.current = el }}
          data={chart.spec.data ?? []}
          layout={plotLayout}
          useResizeHandler
          style={{ width: '100%', height: `${chartHeight}px` }}
          config={{ displayModeBar: false, responsive: true, scrollZoom: true }}
        />
      </div>
      <Modal open={expanded} onClose={() => setExpanded(false)} size="large">
        {expanded && (
          <div className="relative">
            <div className="absolute top-0 right-0 z-10 flex gap-2">
              <button onClick={handleModalAutoscale} title="Reset scale" className="bg-surface text-fg hover:bg-accent hover:text-accent-fg text-xs font-mono px-2 py-1 rounded transition-colors border border-muted">
                Reset Scale
              </button>
              <button onClick={handleSaveImage} title="Save as image" className="bg-surface text-fg hover:bg-accent hover:text-accent-fg text-xs font-mono px-2 py-1 rounded transition-colors border border-muted">
                Download Image
              </button>
              <button onClick={() => setExpanded(false)} title="Close" className="bg-surface text-fg hover:bg-danger hover:text-white text-xs font-mono px-2 py-1 rounded transition-colors border border-muted">
                X
              </button>
            </div>
            <Plot
              ref={el => { modalGdRef.current = el }}
              data={chart.spec.data ?? []}
              layout={plotLayout}
              useResizeHandler
              style={{ width: '100%', height: '70vh' }}
              config={{ displayModeBar: false, responsive: true, scrollZoom: true }}
            />
          </div>
        )}
      </Modal>
    </div>
  )
}

export default function SharePage() {
  const { datasetId } = useParams()  
  const [dark, setDark] = useTheme()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getPublicDashboard(datasetId)
      .then(res => setData(res))
      .catch(() => setError('This dashboard is not available.'))
  }, [datasetId])
  
  useEffect(() => {
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    document.head.appendChild(meta)
    return () => document.head.removeChild(meta)
  }, [])

  return (
    <div className={dark ? 'dark' : ''}>
      <div className="min-h-screen bg-bg text-fg transition-colors duration-300 flex flex-col">
        <header className="border-b border-muted px-10 py-[26px] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src={dark ? '/dasher2-dark.svg' : '/dasher2-light.svg'} alt="Dasher" className="w-8 h-8 shrink-0" />
            <span className="font-display font-medium text-[18px] tracking-wide uppercase text-fg">
              Dasher
            </span>
          </div>
          <div onClick={() => setDark(d => !d)} className="flex items-center gap-2.5 cursor-pointer select-none">
            <span className={`font-mono text-[11px] font-medium tracking-wide transition-opacity ${dark ? 'opacity-40' : 'opacity-100'} text-muted`}>
              LIGHT
            </span>
            <div className="w-10 h-[22px] rounded-full border border-muted bg-bg relative box-border">
              <div className={`w-4 h-4 rounded-full bg-accent absolute top-[2px] transition-all duration-150 ${dark ? 'left-[21px]' : 'left-[2px]'}`} />
            </div>
            <span className={`font-mono text-[11px] font-medium tracking-wide transition-opacity ${dark ? 'opacity-100' : 'opacity-40'} text-muted`}>
              DARK
            </span>
          </div>
        </header>

        <div className="flex-1 max-w-6xl w-full mx-auto px-10">
          {error && (
            <p className="font-mono text-sm text-muted mt-16">{error}</p>
          )}

          {!error && !data && (
            <p className="font-mono text-xs text-muted animate-pulse mt-16">
              Loading dashboard...
            </p>
          )}

          {data && (
            <>
              <div className="pt-9 pb-2 flex flex-col gap-2">
                <div className="font-mono font-semibold text-[10.5px] uppercase tracking-wider text-muted">
                  Shared Dashboard
                </div>
                <div className="font-display font-medium text-2xl text-fg">
                  {data.dashboard_title || data.dataset_name || 'Untitled dashboard'}
                </div>
                {data.published_at && (
                  <div className="font-mono text-[12.5px] text-muted">
                    Updated {timeAgo(data.published_at)}
                  </div>
                )}
              </div>

              {data.rationale && (
                <div className="border border-accent/20 rounded-card p-4 my-6 font-mono text-xs text-muted leading-relaxed">
                  {data.rationale}
                </div>
              )}

              <div className="py-7 grid grid-cols-1 md:grid-cols-3 gap-6">
                {(data.charts ?? []).map((chart, i) => (
                  <div key={chart.chart_title ?? i} >
                    <PublicChartCard chart={chart} />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

      <Footer user={undefined} datasetId={datasetId} />
      </div>
    </div>
  )
}