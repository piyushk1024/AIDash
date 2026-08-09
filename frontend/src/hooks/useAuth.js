import { useState, useCallback } from 'react'
import { api } from '../lib/api'

const TOKEN_KEY = 'dasher_token'
const USER_KEY  = 'dasher_user'

function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY)
}

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY))
  } catch {
    return null
  }
}

export function useAuth() {
  const [token, setToken] = useState(getStoredToken)
  const [user, setUser]   = useState(getStoredUser)

  function persist(token, user) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    setToken(token)
    setUser(user)
  }

  function clear() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }

  const login = useCallback(async (username, password) => {
    const data = await api.login(username, password)
    persist(data.access_token, { username: data.username, role: data.role, is_privileged: data.is_privileged })
  }, [])

  const register = useCallback(async (username, password) => {
    await api.register(username, password)
  }, [])

  const logout = useCallback(() => {
    clear()
  }, [])

  return {
    token,
    user,
    isAuthenticated: !!token,
    login,
    register,
    logout,
  }
}