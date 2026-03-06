import { useState } from 'react'
import { Menu, X } from 'lucide-react'
import copy from '../copy'
import Sidebar from './Sidebar'
import ThemeToggleButton from './ThemeToggleButton'

const SIDEBAR_STORAGE_KEY = 'insta-sum-sidebar-collapsed'

export default function AppShell({
  children,
  history,
  activeUsername,
  currentUser,
  onSearch,
  searching,
  onLogout,
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') {
      return false
    }
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1'
  })

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, next ? '1' : '0')
      return next
    })
  }

  const expandSidebar = () => {
    setCollapsed(false)
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, '0')
  }

  return (
    <div className="app-shell">
      <div className="shell-floating-actions">
        <ThemeToggleButton />
      </div>

      <button
        type="button"
        className="mobile-menu-btn"
        aria-label={copy.common.openMenu}
        onClick={() => setMobileOpen(true)}
      >
        <Menu size={20} />
      </button>

      {mobileOpen && (
        <button
          type="button"
          className="mobile-backdrop"
          aria-label={copy.common.closeMenu}
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside className={`shell-sidebar ${mobileOpen ? 'open' : ''} ${collapsed ? 'collapsed' : ''}`}>
        <div className="mobile-sidebar-head">
          <button
            type="button"
            className="icon-only"
            aria-label={copy.common.closeMenu}
            onClick={() => setMobileOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <Sidebar
          history={history}
          activeUsername={activeUsername}
          currentUser={currentUser}
          onSearch={onSearch}
          searching={searching}
          onLogout={onLogout}
          onNavigate={() => setMobileOpen(false)}
          collapsed={collapsed}
          onToggleCollapse={toggleCollapsed}
          onExpandSearch={expandSidebar}
        />
      </aside>

      <main className={`shell-main ${collapsed ? 'collapsed' : ''}`}>
        <div className="shell-main-inner">{children}</div>
      </main>
    </div>
  )
}
