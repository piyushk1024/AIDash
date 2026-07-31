import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate, useParams, useLocation } from 'react-router'
import { useAuth } from './hooks/useAuth'
import { useDasher } from './hooks/useDasher'
import { api } from './lib/api'
import AuthPage from './components/AuthPage'
import SharePage from './components/sharepage'
import LaunchCard from './components/steps/LaunchCard'
import Workspace from './components/steps/Workspace'
import { useTheme } from './hooks/useTheme'

function Header({ showHome, onGoHome, user, onLogout, dark, onToggleDark }) {
  return (
    <header className="border-b border-muted px-10 py-[26px] flex items-center justify-between sticky top-0 bg-bg z-10">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 bg-accent rounded-[4px] rotate-45 shrink-0" />
        <span className="font-display font-medium text-[18px] tracking-wide uppercase text-fg">
          Dasher
        </span>
      </div>
      <div className="flex items-center gap-4">
        {showHome && (
          <button
            onClick={onGoHome}
            className="flex items-center gap-1.5 font-mono text-xs text-muted hover:text-accent transition-colors tracking-wider uppercase group"
          >
            <span className="group-hover:-translate-x-0.5 transition-transform duration-150">←</span>
            <span>Home</span>
          </button>
        )}
        <span className="font-mono text-xs text-muted">
          {user?.username}
        </span>
        <button
          onClick={onLogout}
          className="font-mono text-xs text-muted hover:text-accent transition-colors tracking-wider uppercase"
        >
          Sign out
        </button>
        {/* <button
          onClick={() => onToggleDark()}
          className="w-8 h-8 flex items-center justify-center rounded-icon border border-muted hover:border-accent transition-colors"
          title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          <span className="text-muted text-xs">{dark ? '☀' : '☾'}</span>
        </button> */}
        <div
          onClick={onToggleDark}
          className="flex items-center gap-2.5 cursor-pointer select-none"
        >
          <span className={`font-mono text-[11px] font-medium tracking-wide transition-opacity ${dark ? 'opacity-40' : 'opacity-100'} text-muted`}>
            LIGHT
          </span>
          <div className="w-10 h-[22px] rounded-full border border-muted bg-bg relative box-border">
            <div
              className={`w-4 h-4 rounded-full bg-accent absolute top-[2px] transition-all duration-150 ${dark ? 'left-[21px]' : 'left-[2px]'}`}
            />
          </div>
          <span className={`font-mono text-[11px] font-medium tracking-wide transition-opacity ${dark ? 'opacity-100' : 'opacity-40'} text-muted`}>
            DARK
          </span>
        </div>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route path="/share/:datasetId" element={<SharePage />} />
      <Route path="/" element={<DasherApp />} />
      <Route path="/launch" element={<DasherApp />} />
      <Route path="/d/:datasetId" element={<DasherApp />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function DasherApp() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { datasetId: routeDatasetId } = useParams()
  const [dark, setDark] = useTheme()
  const [datasets, setDatasets] = useState([])
  const [picking, setPicking] = useState(true)
  // const [hydrating, setHydrating] = useState(false)
  
  const dasher = useDasher()
  const { rehydrate } = dasher

  const hydrating = Boolean(routeDatasetId) && auth.isAuthenticated && dasher.datasetId !== routeDatasetId

  const isLaunchRoute = location.pathname === '/launch'
  const isWorkspaceRoute = Boolean(routeDatasetId)

  useEffect(() => {
    if (!auth.isAuthenticated) return
    api.listDatasets()
      .then(res => setDatasets(res.datasets ?? []))
      .catch(() => setDatasets([]))
      .finally(() => setPicking(false))
  }, [auth.isAuthenticated])

  // Rehydrate whenever the route names a dataset the client doesn't already
  // have loaded — covers a hard refresh on /d/:id, and direct navigation
  // (e.g. a bookmarked link). Redirects home if the id turns out to be bad.
  useEffect(() => {
    if (!auth.isAuthenticated || !routeDatasetId) return
    if (dasher.datasetId === routeDatasetId) return
    // rehydrate(routeDatasetId).
    rehydrate(routeDatasetId).then(ok => {      
      if (!ok) navigate('/', { replace: true })
    })
  }, [auth.isAuthenticated, routeDatasetId])

  if (!auth.isAuthenticated) return <Navigate to="/login" replace />

  function handlePickDataset(datasetId) {
    navigate(`/d/${datasetId}`)
  }

  function handleStartFresh() {
    dasher.reset()
    navigate('/launch')
  }

  async function handleDeleteDataset(datasetId) {
    await api.deleteDataset(datasetId)
    setDatasets(prev => prev.filter(d => d.dataset_id !== datasetId))
  }

  function handleGoHome() {
    api.listDatasets()
      .then(res => setDatasets(res.datasets ?? []))
      .catch(() => {})
    dasher.reset()
    navigate('/')
  }

  async function handleLaunchDone(datasetId) {
    const res = await api.listDatasets().catch(() => null)
    if (res) setDatasets(res.datasets ?? [])
    if (datasetId) navigate(`/d/${datasetId}`)
  }

  const showHome = isLaunchRoute || isWorkspaceRoute

  if (!isLaunchRoute && !isWorkspaceRoute) {
    return (
      <div className={dark ? 'dark' : ''}>
        <div className="min-h-screen bg-bg text-fg transition-colors duration-300">
          <Header
            showHome={showHome}
            onGoHome={handleGoHome}
            user={auth.user}
            onLogout={auth.logout}
            dark={dark}
            onToggleDark={() => setDark(d => !d)}
          />
          <div className="max-w-xl mx-auto px-8 py-16">
            <h1 className="font-mono text-[10.5px] tracking-wider uppercase text-muted mb-1">
              AI-Enabled Dashboarding
            </h1>
            <p className="font-display font-semibold text-2xl text-fg mb-10">
              Continue a dataset or start fresh
            </p>
            {picking ? (
              <p className="font-mono text-xs text-muted animate-pulse">Loading datasets...</p>
            ) : (
              <div className="flex flex-col gap-2">
                {datasets.length === 0 && (
                  <p className="font-mono text-xs text-muted mb-2">No datasets yet.</p>
                )}
                {datasets.map(ds => (
                  <div key={ds.dataset_id} className="flex items-center gap-2">
                    <button
                      onClick={() => handlePickDataset(ds.dataset_id)}
                      className="flex-1 text-left px-4 py-3 rounded-card border border-muted hover:border-accent hover:bg-accent-wash-soft font-mono text-sm transition-all duration-150"
                    >
                      <span className="text-fg">{ds.name || ds.original_filename}</span>
                      <span className="ml-3 text-xs text-muted">{ds.dataset_id.slice(0, 8)}</span>
                    </button>
                    <button
                      onClick={() => handleDeleteDataset(ds.dataset_id)}
                      title="Delete dataset"
                      className="w-9 h-9 flex items-center justify-center rounded-icon border border-transparent hover:border-danger/40 hover:text-danger font-mono text-xs text-muted transition-all duration-150"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  onClick={handleStartFresh}
                  className="mt-4 text-left px-4 py-3 rounded-card border border-dashed border-muted hover:border-accent hover:bg-accent-wash-soft font-mono text-sm text-muted hover:text-accent transition-all duration-150"
                >
                  + Start fresh
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={dark ? 'dark' : ''}>
      <div className="min-h-screen bg-bg text-fg transition-colors duration-300">
        <Header
          showHome={showHome}
          onGoHome={handleGoHome}
          user={auth.user}
          onLogout={auth.logout}
          dark={dark}
          onToggleDark={() => setDark(d => !d)}
        />
        {isWorkspaceRoute ? (
          hydrating ? (
            <div className="max-w-xl mx-auto px-8 py-16">
              <p className="font-mono text-xs text-muted animate-pulse">Loading dashboard...</p>
            </div>
          ) : (
            <Workspace dasher={dasher} />
          )
        ) : (
          <div className="max-w-5xl mx-auto px-8 py-16">
            <LaunchCard dasher={dasher} onDone={handleLaunchDone} />
          </div>
        )}
      </div>
    </div>
  )
}