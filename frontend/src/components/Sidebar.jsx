import { useMemo, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  LogOut,
  Search,
  User,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import copy from '../copy'
import BrandLogo from './BrandLogo'
import { resolveImageSrc } from '../lib/media'
import ProfileSearchForm from './ProfileSearchForm'

export default function Sidebar({
  history,
  activeUsername,
  currentUser,
  onSearch,
  searching,
  onLogout,
  onNavigate,
  collapsed,
  onToggleCollapse,
  onExpandSearch,
}) {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  const recentProfiles = useMemo(() => (history || []).slice(0, 10), [history])

  const submit = async (value) => {
    if (!value.trim()) return
    try {
      await onSearch(value)
      setQuery('')
    } catch {
      // toast already shown by caller
    }
  }

  const openHistory = (username) => {
    if (!username) return
    navigate(`/profile/${username}`)
    onNavigate?.()
  }

  const goHome = () => {
    navigate('/dashboard')
    onNavigate?.()
  }

  const logout = async () => {
    await onLogout()
    onNavigate?.()
  }

  return (
    <div className="sidebar-inner">
      <div className="sidebar-topbar">
        <button type="button" className="sidebar-logo-btn" onClick={goHome} aria-label={copy.sidebar.homeAria}>
          <BrandLogo compact={collapsed} className="sidebar-logo" />
        </button>
        <div className="sidebar-top-actions">
          <button type="button" className="ghost-icon-btn sidebar-collapse-btn" onClick={onToggleCollapse} aria-label={copy.sidebar.toggleSidebar}>
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>
      </div>

      {collapsed ? (
        <button type="button" className="sidebar-quick-action" onClick={onExpandSearch} aria-label={copy.sidebar.expandSearch}>
          <Search size={20} />
        </button>
      ) : (
        <div className="sidebar-search">
          <ProfileSearchForm
            value={query}
            onChange={setQuery}
            onSubmit={submit}
            searching={searching}
            placeholder={copy.sidebar.searchPlaceholder}
            variant="compact"
          />
        </div>
      )}

      <div className="sidebar-history-head">
        <Clock size={16} />
        <span>{copy.sidebar.historyHeading}</span>
      </div>

      <div className="sidebar-history-list">
        {recentProfiles.length === 0 && <div className="sidebar-empty">{copy.sidebar.historyEmpty}</div>}
        {recentProfiles.map((item) => {
          const active = item.username === activeUsername
          return (
            <button
              key={item.id}
              type="button"
              className={`history-item ${active ? 'active' : ''}`}
              onClick={() => openHistory(item.username)}
            >
              {item.avatar_url ? (
                <img
                  src={resolveImageSrc(item.avatar_url)}
                  alt={copy.common.profileAvatarAlt({ username: item.username })}
                  className="history-avatar"
                  loading="lazy"
                />
              ) : (
                <div className="history-avatar fallback">
                  <User size={16} />
                </div>
              )}
              <div className="history-text">
                <div className="history-username">@{item.username}</div>
                <div className="history-meta">
                  {copy.sidebar.processedMeta({
                    processed: item.processed_count || 0,
                    total: item.reels_count || 0,
                  })}
                </div>
              </div>
              <ChevronRight size={16} />
            </button>
          )
        })}
      </div>

      <div className="sidebar-user-footer">
        <div className="user-pill" title={currentUser?.email || ''}>
          <User size={16} />
          <span>{currentUser?.email || copy.sidebar.guestEmail}</span>
        </div>
        <div className="sidebar-footer-actions">
          <button type="button" className="ghost-icon-btn" onClick={logout} aria-label={copy.sidebar.logoutTooltip} title={copy.sidebar.logoutTooltip}>
            <LogOut size={20} />
          </button>
        </div>
      </div>
    </div>
  )
}
