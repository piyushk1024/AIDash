import { useState, useEffect } from 'react'
import { api } from '../../lib/api'
import { getQuotaState, subscribeQuota, setQuotaState } from '../../lib/quotaStore'

export default function QuotaBadge() {
  const [quota, setQuota] = useState(getQuotaState())

  useEffect(() => {
    const unsubscribe = subscribeQuota(setQuota)
    api.getQuotaStatus().then(setQuotaState).catch(() => {})
    return unsubscribe
  }, [])

  if (quota.unlimited || quota.limit === null) return null

  return (
    <div className="fixed bottom-7 left-7 z-40 flex items-center gap-2 bg-surface border border-muted rounded-full px-4 py-2 shadow-lg">
      <div className="w-2 h-2 rounded-full bg-accent shrink-0" />
      <span className="font-mono text-xs text-muted">
        {quota.remaining}/{quota.limit} calls left
      </span>
    </div>
  )
}