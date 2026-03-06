import { useCallback, useState } from 'react'
import { apiFetch } from '../lib/api'

export function useApi() {
  const [loading, setLoading] = useState(false)

  const request = useCallback(async (path, options = {}) => {
    setLoading(true)
    try {
      return await apiFetch(path, options)
    } finally {
      setLoading(false)
    }
  }, [])

  return { request, loading }
}
