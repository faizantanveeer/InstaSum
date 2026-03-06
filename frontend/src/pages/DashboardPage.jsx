import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { HomeEmptyState } from '../components/States'
import copy from '../copy'
import { useWorkspace } from '../hooks/useWorkspace'
import { apiFetch } from '../lib/api'
import { resolveImageSrc } from '../lib/media'

export default function DashboardPage() {
  const { user, history, searching, searchProfile, logoutUser } = useWorkspace()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [recentProfiles, setRecentProfiles] = useState([])

  useEffect(() => {
    document.title = copy.titles.home
  }, [])

  useEffect(() => {
    let active = true

    async function loadRecentProfiles() {
      const selected = (history || []).slice(0, 4)
      const enriched = await Promise.all(
        selected.map(async (item) => {
          try {
            const data = await apiFetch(`/api/profiles/${item.username}?page=1&page_size=1`)
            return {
              ...item,
              avatar_url: resolveImageSrc(item.avatar_url),
              followers_abbr: data?.profile?.followers_abbr || '',
            }
          } catch {
            return {
              ...item,
              avatar_url: resolveImageSrc(item.avatar_url),
              followers_abbr: '',
            }
          }
        }),
      )

      if (active) {
        setRecentProfiles(enriched)
      }
    }

    loadRecentProfiles().catch(() => {
      if (active) {
        setRecentProfiles([])
      }
    })

    return () => {
      active = false
    }
  }, [history])

  return (
    <AppShell
      history={history}
      activeUsername=""
      currentUser={user}
      onSearch={searchProfile}
      searching={searching}
      onLogout={logoutUser}
    >
      <div className="page-panel home-panel">
        <HomeEmptyState
          query={query}
          onQueryChange={setQuery}
          onSearch={searchProfile}
          searching={searching}
          recentProfiles={recentProfiles}
          onOpenProfile={(username) => navigate(`/profile/${username}?page=1`)}
        />
      </div>
    </AppShell>
  )
}
