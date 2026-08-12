import FeedbackFab from './steps/FeedbackFab'

function obfuscatedEmail(user, domain) {
  return `${user} [at] ${domain} [dot] com`
}

export default function Footer({ user, datasetId }) {
  return (
    <footer className="border-t border-muted mt-auto">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4 text-xs text-muted">
          <span className="font-mono text-xs text-muted">
            Made with <span className="font-display font-semibold text-fg">Dasher</span>
          </span>
          <span>Made by <span className="font-display font-semibold text-fg">Piyush K.</span></span>
          <span className="select-all font-display font-semibold text-fg">{obfuscatedEmail('piyushk256', 'gmail')}</span>
          <a href="https://www.linkedin.com/in/piyushk256/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline transition-colors">
            <span className="font-display font-semibold">My LinkedIn</span>
          </a>
        </div>
        <div className="flex items-center gap-3">
          {!user && (
            <a href="/login"
              className="px-4 py-2.5 rounded-icon font-display font-semibold text-xs tracking-wide uppercase bg-accent text-accent-fg"
            >
              Make your own dashboard
            </a>
          )}
          {user && <FeedbackFab user={user} datasetId={datasetId} />}
        </div>
      </div>
    </footer>
  )
}