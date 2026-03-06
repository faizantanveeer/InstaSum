import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refreshMe = useCallback(async () => {
    setLoading(true)
    try {
      const me = await apiFetch('/api/auth/me')
      setUser(me)
      return me
    } catch (error) {
      if (error.status === 401) {
        setUser(null)
        return null
      }
      throw error
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshMe().catch(() => {
      setLoading(false)
    })
  }, [refreshMe])

  const login = useCallback(async (email, password) => {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    if (data?.user) {
      setUser(data.user)
    } else {
      await refreshMe()
    }
    return data
  }, [refreshMe])

  const signup = useCallback(async (email, password, confirmPassword) => {
    const data = await apiFetch('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        confirm_password: confirmPassword,
      }),
    })
    if (data?.user) {
      setUser(data.user)
    } else {
      await refreshMe()
    }
    return data
  }, [refreshMe])

  const logout = useCallback(async () => {
    await apiFetch('/api/auth/logout', { method: 'POST' })
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, authenticated: !!user, refreshMe, login, signup, logout }),
    [user, loading, refreshMe, login, signup, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}
