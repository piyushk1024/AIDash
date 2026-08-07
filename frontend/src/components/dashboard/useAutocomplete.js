import { useState } from 'react'

export function useAutocomplete(fieldMap) {
  const [value, setValue] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [selectedColumns, setSelectedColumns] = useState([])

  function handleChange(raw) {
    setValue(raw)
    const lastWord = raw.split(' ').pop().toLowerCase()
    if (lastWord.length < 1) { setSuggestions([]); return }
    const keys = Object.keys(fieldMap ?? {})
    setSuggestions(keys.filter(k => k.toLowerCase().includes(lastWord)).slice(0, 6))
  }

  function onSelect(col) {
    const parts = value.split(' ')
    parts[parts.length - 1] = col
    setValue(parts.join(' ') + ' ')
    setSuggestions([])
    setSelectedColumns(prev => prev.includes(col) ? prev : [...prev, col])
  }

  function reset() { setValue(''); setSuggestions([]); setSelectedColumns([]) }

  return { value, handleChange, suggestions, selectedColumns, onSelect, reset }
}