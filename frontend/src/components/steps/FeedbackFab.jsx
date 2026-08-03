import { useState } from 'react'
import { api } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import Modal from '../Modal'

const TYPES = [
  { id: 'idea', label: 'FEATURE', placeholder: 'e.g. it would help to export a card as an image' },
  { id: 'bug', label: 'BUG', placeholder: "e.g. the churn chart shows the wrong date range" },
  { id: 'other', label: 'OTHER', placeholder: "tell us what's on your mind" },
]

export default function FeedbackFab({ user, datasetId }) {
  const [open, setOpen] = useState(false)
  const [type, setType] = useState('idea')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const toast = useToast()

  function reset() {
    setType('idea')
    setMessage('')
  }

  function close() {
    setOpen(false)
    reset()
  }

  async function handleSubmit() {
    setSubmitting(true)
    try {
      await api.submitFeedback(type, message || null, datasetId || null)
      toast.success('Feedback sent, thank you.')
      close()
    } catch {
      toast.error('Could not send feedback. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const activeType = TYPES.find(t => t.id === type)

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-7 right-7 z-40 flex items-center gap-2.5 bg-surface border border-muted rounded-full px-4.5 py-2.5 shadow-lg hover:border-accent transition-colors"
      >
        <div className="w-2 h-2 rounded-full bg-accent shrink-0" />
        <span className="font-display font-semibold text-xs tracking-wide uppercase text-fg">Feedback</span>
      </button>

      <Modal open={open} onClose={close}>
        <div className="flex items-center justify-between mb-5">
          <span className="font-display font-semibold text-sm tracking-wide uppercase text-fg">Send Feedback</span>
        </div>

        <div className="mb-5">
          <div className="font-mono font-semibold text-[10.5px] tracking-wide uppercase text-muted mb-2">Type</div>
          <div className="flex border border-muted rounded-control p-1 gap-1 bg-bg">
            {TYPES.map(t => (
              <button
                key={t.id}
                onClick={() => setType(t.id)}
                className={`flex-1 text-center py-2 rounded-icon font-display text-xs transition-colors ${
                  type === t.id ? 'bg-accent text-white font-semibold' : 'text-muted'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-5">
          <div className="font-mono font-semibold text-[10.5px] tracking-wide uppercase text-muted mb-2">
            What's going on? <span className="normal-case font-medium opacity-70">(optional detail)</span>
          </div>
          <textarea
            value={message}
            onChange={e => setMessage(e.target.value)}
            placeholder={activeType.placeholder}
            className="w-full border border-muted rounded-control bg-bg px-3 py-2.5 text-xs text-fg placeholder:text-muted min-h-[64px] font-mono"
          />
        </div>

        <div className="flex items-center gap-2.5 text-xs text-muted mb-6">
          <span>{user?.username}</span>
        </div>

        <div className="flex items-center justify-end gap-2.5">
          <button onClick={close} className="px-3.5 py-2 font-display text-xs font-medium text-muted hover:text-fg transition-colors">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4.5 py-2 rounded-control bg-accent text-white font-display text-xs font-semibold tracking-wide uppercase disabled:opacity-50"
          >
            {submitting ? 'Sending...' : 'Send Feedback'}
          </button>
        </div>
      </Modal>
    </>
  )
}