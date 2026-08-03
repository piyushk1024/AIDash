import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAuth } from '../hooks/useAuth'
import { useTheme } from '../hooks/useTheme'

export default function AuthPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [dark, setDark] = useTheme()

  const [mode, setMode] = useState('login')   // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [registered, setRegistered] = useState(false)

  const isRegistering = mode === 'register'
  const passwordsMismatch = isRegistering && confirmPassword.length > 0 && password !== confirmPassword
  const canSubmit = username.trim() && password.trim() && !(isRegistering && (!confirmPassword.trim() || passwordsMismatch))

  async function handleSubmit() {
    if (!canSubmit) return
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

  function switchMode() {
    setMode(m => m === 'login' ? 'register' : 'login')
    setError(null)
    setRegistered(false)
    setConfirmPassword('')
  }

  return (
    <div className={dark ? 'dark' : ''}>
      <div className="min-h-screen bg-bg flex">

        {/* Left — marketing panel */}
        <div className="hidden lg:flex flex-1 flex-col justify-center gap-7 px-16 relative min-w-0">
          <div className="absolute top-10 left-16 flex items-center gap-3">
            <div className="w-4 h-4 bg-accent rounded-[4px] rotate-45 shrink-0" />
            <span className="font-display font-medium text-[18px] text-fg">DASHER</span>
          </div>

          <div className="flex items-center gap-2.5 w-fit bg-surface border border-muted rounded-full px-4 py-2.5 font-mono text-xs text-muted">
            <span className="text-accent font-bold">$</span>
            <span>dasher --input revenue.csv --infer --build</span>
            <span className="w-[7px] h-[13px] bg-accent opacity-85 animate-pulse shrink-0" />
          </div>

          <h1 className="font-display font-extrabold text-5xl leading-[1.06] text-fg tracking-tight">
            Drop a CSV.<br />
            Get a <span className="text-accent">dashboard.</span>
          </h1>
          <p className="font-mono text-[14.5px] leading-relaxed text-muted max-w-[440px]">
            Dasher profiles your data, infers what matters, and builds charts you steer with plain language — no schema mapping, no chart builder.
          </p>

          <div className="flex gap-9 mt-2">
            <div className="flex flex-col gap-1">
              <span className="font-display font-bold text-2xl text-fg">&lt;2 MIN</span>
              <span className="font-mono text-[10.5px] font-semibold tracking-wide uppercase text-muted">CSV to charts</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-display font-bold text-2xl text-fg">0</span>
              <span className="font-mono text-[10.5px] font-semibold tracking-wide uppercase text-muted">Manual chart config</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-display font-bold text-2xl text-fg">1</span>
              <span className="font-mono text-[10.5px] font-semibold tracking-wide uppercase text-muted">Steering hint away</span>
            </div>
          </div>
        </div>

        {/* Right — auth panel, same mode as the page, one elevation up */}
        <div className="flex-1 lg:flex-none lg:w-[480px] bg-surface flex flex-col items-center justify-center px-14 relative">
          <div
            onClick={() => setDark(d => !d)}
            className="absolute top-10 right-12 flex items-center gap-2.5 cursor-pointer select-none"
          >
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

          <div className="w-full max-w-[360px] flex flex-col gap-4">
            <h2 className="font-display font-semibold text-lg text-fg">
              {mode === 'login' ? 'Welcome back' : 'Create account'}
            </h2>

            {registered && (
              <div className="font-mono text-xs text-accent">✓ Account created — sign in below.</div>
            )}

            <div className="flex flex-col gap-1.5">
              <label className="font-mono font-semibold text-[10px] uppercase tracking-wider text-muted">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                onKeyDown={handleKeyDown}
                autoComplete="username"
                disabled={loading}
                className="w-full bg-bg border border-muted rounded-control px-3.5 py-2.5 font-mono text-[13px] text-fg focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-mono font-semibold text-[10px] uppercase tracking-wider text-muted">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={handleKeyDown}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                disabled={loading}
                className="w-full bg-bg border border-muted rounded-control px-3.5 py-2.5 font-mono text-[13px] text-fg focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
              />
            </div>

            {isRegistering && (
              <div className="flex flex-col gap-1.5">
                <label className="font-mono font-semibold text-[10px] uppercase tracking-wider text-muted">Confirm password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  onKeyDown={handleKeyDown}
                  autoComplete="new-password"
                  disabled={loading}
                  className={`w-full bg-bg border rounded-control px-3.5 py-2.5 font-mono text-[13px] text-fg focus:outline-none transition-colors disabled:opacity-50 ${passwordsMismatch ? 'border-danger' : 'border-muted focus:border-accent'}`}
                />
                {passwordsMismatch && (
                  <span className="font-mono text-[11px] text-danger">Passwords don't match.</span>
                )}
              </div>
            )}

            {error && (
              <div className="font-mono text-[12px] text-danger">✕ {error}</div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading || !canSubmit}
              className="mt-1 w-full py-2.5 rounded-control font-display text-[13px] font-semibold uppercase tracking-wide transition-colors border border-muted text-fg disabled:opacity-70 disabled:cursor-not-allowed enabled:bg-accent enabled:text-accent-fg enabled:border-transparent enabled:cursor-pointer"
            >
              {loading ? '…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>

            <button
              onClick={switchMode}
              className="font-mono text-xs text-accent hover:opacity-80 transition-opacity text-center"
            >
              {mode === 'login' ? 'New here? Create an account' : '← Back to sign in'}
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}