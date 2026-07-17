import StepHeader from './StepHeader'

// Generic shell for a completed wizard step: a clickable summary row
// (label, summary content, checkmark, expand chevron) plus an optional
// expanded detail panel below it. Upload/Semantics/Plan steps all share
// this exact shape — only the label and summary/expanded content differ.
export function StepDoneRow({ label, summary, isExpanded, onToggle, children }) {
  return (
    <div className="animate-fade-in">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center gap-3 font-mono text-xs text-left rounded border border-transparent hover:border-neutral-200 dark:hover:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900 transition-all duration-150 cursor-pointer"
        title="Click to expand"
      >
        <span className="text-neutral-500 uppercase tracking-wider">{label}</span>
        <span className="text-neutral-300 dark:text-neutral-600">—</span>
        {summary}
        <span className="text-amber-400 ml-auto">✓</span>
        <span className={`text-neutral-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {isExpanded && (
        <div className="animate-fade-in mx-1 mb-3 px-4 py-3 border border-neutral-200 dark:border-neutral-800 rounded-b bg-neutral-50 dark:bg-neutral-900/50">
          {children}
        </div>
      )}
    </div>
  )
}

// Generic shell for a step's active (pre-completion) form: the amber-bordered
// box wrapping StepHeader + description + the step's own form/button content.
export function StepActiveShell({ title, description, children }) {
  return (
    <div className="animate-fade-in mt-6">
      <div className="rounded-lg border border-amber-400/30 bg-amber-400/[0.02] dark:bg-amber-400/[0.03] px-6 py-5">
        <StepHeader title={title} />
        {description && (
          <p className="font-mono text-xs text-neutral-500 mt-1 mb-5">{description}</p>
        )}
        {children}
      </div>
    </div>
  )
}