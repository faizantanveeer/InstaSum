import { Loader2, Search, X } from 'lucide-react'
import copy from '../copy'
import { normalizeProfileInput } from '../lib/profile'

export default function ProfileSearchForm({
  value,
  onChange,
  onSubmit,
  searching = false,
  placeholder = 'Username or URL',
  variant = 'compact',
  buttonLabel = 'Search',
}) {
  const hasValue = Boolean(value.trim())
  const normalized = normalizeProfileInput(value) || value.trim().replace(/^@/, '') || 'profile'
  const loadingTitle = variant === 'compact'
    ? copy.sidebar.searchLoadingTitle
    : copy.loading.searchInProgress({ username: normalized })

  const submit = (event) => {
    event.preventDefault()
    if (!hasValue || searching) {
      return
    }
    onSubmit(value)
  }

  return (
    <form className={`profile-search-form ${variant}`} onSubmit={submit}>
      <div className="search-input-shell">
        <Search size={variant === 'hero' ? 20 : 16} className="search-leading-icon" />
        <input
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          aria-busy={searching}
          disabled={searching}
        />
        <div className="search-slot" aria-hidden="true">
          <button
            type="button"
            className={`search-slot-button ${hasValue && !searching ? 'is-visible' : ''}`}
            onClick={() => onChange('')}
            tabIndex={hasValue && !searching ? 0 : -1}
            aria-label={copy.common.clearSearch}
          >
            <X size={16} />
          </button>
          <span className={`search-slot-spinner ${searching ? 'is-visible' : ''}`} title={searching ? loadingTitle : undefined}>
            <Loader2 size={16} className="spin" />
          </span>
        </div>
      </div>

      {variant === 'hero' ? (
        <button type="submit" className="btn-primary hero-search-button" disabled={searching || !hasValue}>
          {searching ? <Loader2 size={20} className="spin" /> : <Search size={20} />}
          <span>{buttonLabel}</span>
        </button>
      ) : null}
    </form>
  )
}
