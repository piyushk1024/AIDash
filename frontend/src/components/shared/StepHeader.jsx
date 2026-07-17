export default function StepHeader({ title, className = 'mb-1' }) {
  return (
    <h2 className={`font-mono text-sm tracking-widest uppercase text-neutral-900 dark:text-neutral-100 ${className}`}>
      {title}
    </h2>
  )
}