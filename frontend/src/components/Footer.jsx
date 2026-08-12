import FeedbackFab from './steps/FeedbackFab'

export default function Footer({ user, datasetId }) {
  return (
    <footer className="border-t border-muted mt-auto">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-muted">
        <div className="flex items-center gap-4">
          <span>Made by Piyush K.</span>
          <a href="mailto:you@example.com" className="hover:text-fg transition-colors">
            piyushk256@gmail.com
          </a>
          <a
            href="https://www.linkedin.com/in/piyushk256/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-fg transition-colors"          >
            LinkedIn
          </a>
        </div>

        {user && <FeedbackFab user={user} datasetId={datasetId} />}
      </div>
    </footer>
  )
}