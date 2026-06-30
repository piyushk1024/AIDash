import { useState, useCallback } from 'react'
import { getToken } from '../lib/api'

// Parses a raw SSE buffer into individual JSON events.
// Events are separated by a blank line; only "data: " lines are read.
// The last (possibly incomplete) chunk is returned as the new buffer.
function parseSSEBuffer(buffer) {
  const events = []
  const parts = buffer.split('\n\n')
  const remainder = parts.pop()

  for (const part of parts) {
    const line = part.split('\n').find(l => l.startsWith('data: '))
    if (!line) continue
    try {
      events.push(JSON.parse(line.slice(6)))
    } catch {
      // malformed event — skip rather than crash the stream
    }
  }

  return { events, remainder }
}

export function useEventStream() {
  const [events, setEvents] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [streamError, setStreamError] = useState(null)

  // Returns the full collected event array once the stream ends —
  // callers don't have to rely on React state (which batches/lags)
  // to know what just arrived.
  const startStream = useCallback(async (url, body) => {
    setEvents([])
    setStreamError(null)
    setStreaming(true)

    const collected = []

    try {
      const headers = { 'Content-Type': 'application/json' }
      const token = getToken()
      if (token) headers['Authorization'] = `Bearer ${token}`

      const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body ?? {}),
      })

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Stream request failed')
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const { events: parsed, remainder } = parseSSEBuffer(buffer)
        buffer = remainder

        for (const event of parsed) {
          collected.push(event)
          setEvents(prev => [...prev, event])

          if (event.type === 'phase_error') {
            setStreamError(event.error || 'Agent run failed')
          }
        }
      }
    } catch (e) {
      setStreamError(e.message ?? 'Stream failed')
    } finally {
      setStreaming(false)
    }

    return collected
  }, [])

  const reset = useCallback(() => {
    setEvents([])
    setStreaming(false)
    setStreamError(null)
  }, [])

  return { events, streaming, streamError, startStream, reset }
}