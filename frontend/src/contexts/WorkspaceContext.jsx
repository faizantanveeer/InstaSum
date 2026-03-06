import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import copy from '../copy'
import { useAuth } from './AuthContext'
import { useToast } from './ToastContext'
import { apiFetch } from '../lib/api'
import { normalizeProfileInput } from '../lib/profile'

const WorkspaceContext = createContext(null)

export function WorkspaceProvider({ children }) {
  const { user, logout } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()

  const [history, setHistory] = useState([])
  const [searching, setSearching] = useState(false)
  const [pendingSearch, setPendingSearch] = useState(null)

  const mountedRef = useRef(true)

  useEffect(() => {
    return () => {
      mountedRef.current = false
    }
  }, [])

  const loadHistory = useCallback(async () => {
    if (!user) {
      setHistory([])
      return []
    }

    try {
      const data = await apiFetch('/api/profiles')
      const items = data?.profiles || []
      setHistory(items)
      return items
    } catch (error) {
      if (error.status !== 401) {
        toast(error.message || copy.errors.genericServer, 'error')
      }
      return []
    }
  }, [toast, user])

  useEffect(() => {
    loadHistory().catch(() => {})
  }, [loadHistory])

  const searchProfile = useCallback(
    async (profileInput, options = {}) => {
      const guessedUsername = normalizeProfileInput(profileInput)
      if (!guessedUsername) {
        const error = new Error(copy.errors.invalidProfileInput)
        toast(error.message, 'warning')
        throw error
      }

      const nextPending = {
        username: guessedUsername,
        input: profileInput,
        source: options.source || 'search',
        startedAt: Date.now(),
      }

      setSearching(true)
      setPendingSearch(nextPending)
      navigate(`/profile/${guessedUsername}?page=1`)

      try {
        const data = await apiFetch('/api/profiles/search', {
          method: 'POST',
          body: JSON.stringify({ profile_input: profileInput }),
        })

        const resolvedUsername = data?.username || guessedUsername
        await loadHistory()

        if (resolvedUsername !== guessedUsername) {
          navigate(`/profile/${resolvedUsername}?page=1`, { replace: true })
        }

        const reelsCount = Number(data?.reels_count || 0)
        if (data?.source === 'cache') {
          toast(
            options.source === 'refresh'
              ? copy.profile.refreshed({ count: 0 })
              : copy.toasts.profileCached({ username: resolvedUsername }),
            'info',
          )
        } else if (options.source === 'refresh') {
          toast(copy.profile.refreshed({ count: null }), 'success')
        } else {
          toast(copy.toasts.profileLoaded({ n: reelsCount, username: resolvedUsername }), 'success')
        }
        return data
      } catch (error) {
        const fallbackUsername = error?.payload?.username || guessedUsername
        navigate(`/profile/${fallbackUsername}?page=1`, { replace: true })
        if (error.status === 403) {
          toast(copy.toasts.profilePrivate({ username: fallbackUsername }), 'warning')
        } else {
          toast(copy.toasts.profileFetchFailed({ username: fallbackUsername }), 'error')
        }
        throw error
      } finally {
        if (mountedRef.current) {
          setSearching(false)
          setPendingSearch(null)
        }
      }
    },
    [loadHistory, navigate, toast],
  )

  const logoutUser = useCallback(async () => {
    try {
      await logout()
      setHistory([])
      setSearching(false)
      setPendingSearch(null)
      toast(copy.toasts.signedOut, 'info')
      navigate('/login')
    } catch (error) {
      toast(error.message || copy.errors.genericServer, 'error')
    }
  }, [logout, navigate, toast])

  const value = useMemo(
    () => ({
      user,
      history,
      searching,
      pendingSearch,
      searchProfile,
      reloadHistory: loadHistory,
      logoutUser,
    }),
    [history, loadHistory, logoutUser, pendingSearch, searchProfile, searching, user],
  )

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspaceContext() {
  const context = useContext(WorkspaceContext)
  if (!context) {
    throw new Error('useWorkspace must be used inside WorkspaceProvider')
  }
  return context
}
