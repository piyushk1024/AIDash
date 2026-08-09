let listeners = []
let state = { limit: null, remaining: null, unlimited: false }

export function getQuotaState() {
  return state
}

export function setQuotaState(next) {
  state = { ...state, ...next }
  listeners.forEach((fn) => fn(state))
}

export function subscribeQuota(fn) {
  listeners.push(fn)
  return () => { listeners = listeners.filter((l) => l !== fn) }
}