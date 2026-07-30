import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '../hooks/useAuth'

export default function AuthPage() {
  const auth = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState('login')   // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [registered, setRegistered] = useState(false)

  async function handleSubmit() {
    if (!username.trim() || !password.trim()) return
    setLoading(true)
    setError(null)
    try {
      if (mode === 'login') {
        await auth.login(username.trim(), password)
        navigate('/', { replace: true })
      } else {
        await auth.register(username.trim(), password)
        await auth.login(username.trim(), password)
        navigate('/', { replace: true })
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSubmit()
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center">
      <div className="w-full max-w-sm px-8">

        <div className="flex items-center gap-3 mb-10">
          <div className="w-5 h-5 bg-amber-400 rounded-sm rotate-45 shrink-0" />
          <span className="font-mono text-sm tracking-widest uppercase text-neutral-400">
            Dasher
          </span>
        </div>

        <h1 className="font-mono text-2xl text-neutral-100 mb-1">
          {mode === 'login' ? 'Sign in' : 'Create account'}
        </h1>
        <p className="font-mono text-xs text-neutral-500 mb-8">
          {mode === 'login' ? 'Welcome back.' : 'Pick a username and password.'}
        </p>

        {registered && (
          <div className="mb-4 font-mono text-xs text-emerald-400">
            ✓ Account created — sign in below.
          </div>
        )}

        <div className="space-y-3">
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Username"
            autoComplete="username"
            disabled={loading}
            className="w-full bg-transparent border border-neutral-700 rounded px-3 py-2 font-mono text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-400 transition-colors disabled:opacity-50"
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            disabled={loading}
            className="w-full bg-transparent border border-neutral-700 rounded px-3 py-2 font-mono text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-400 transition-colors disabled:opacity-50"
          />
        </div>

        {error && (
          <div className="mt-3 font-mono text-xs text-red-400">✕ {error}</div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading || !username.trim() || !password.trim()}
          className="mt-5 w-full py-2 rounded font-mono text-xs tracking-widest uppercase transition-all duration-200 disabled:bg-neutral-800 disabled:text-neutral-600 disabled:cursor-not-allowed enabled:bg-amber-400 enabled:text-neutral-950 enabled:hover:bg-amber-300 enabled:cursor-pointer"
        >
          {loading ? '...' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>

        <button
          onClick={() => { setMode(m => m === 'login' ? 'register' : 'login'); setError(null); setRegistered(false) }}
          className="mt-4 w-full font-mono text-xs text-neutral-500 hover:text-amber-400 transition-colors"
        >
          {mode === 'login' ? 'No account? Register →' : '← Back to sign in'}
        </button>

      </div>
    </div>
  )
}