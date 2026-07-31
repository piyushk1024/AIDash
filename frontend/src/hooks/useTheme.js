import { useState, useEffect } from 'react'

const THEME_KEY = 'dasher_theme'

export function useTheme() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem(THEME_KEY)
    return saved ? saved === 'dark' : true
  })
  useEffect(() => {
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
  }, [dark])
  return [dark, setDark]
}