import { AlertCircle, Clock, Download, Film, Lock, Mic, Search, Sparkles } from 'lucide-react'
import copy from '../copy'
import BrandLogo from './BrandLogo'
import ProfileSearchForm from './ProfileSearchForm'

export function HomeEmptyState({ query, onQueryChange, onSearch, searching, recentProfiles = [], onOpenProfile }) {
  return (
    <section className="home-screen">
      <div className="home-hero">
        <div className="home-hero-mark">
          <BrandLogo compact className="home-hero-logo" />
        </div>
        <h1 className="home-stacked-headline">
          {copy.home.headline.map((line) => (
            <span key={line}>{line}</span>
          ))}
        </h1>
        <p>{copy.home.subtitle}</p>

        <div className="home-search-wrap">
          <ProfileSearchForm
            value={query}
            onChange={onQueryChange}
            onSubmit={onSearch}
            searching={searching}
            placeholder={copy.home.searchPlaceholder}
            variant="hero"
            buttonLabel={copy.home.searchButton}
          />
        </div>
      </div>

      <section className="home-section recent">
          <div className="section-head">
            <Clock size={24} />
            <h2>{copy.home.recentHeading}</h2>
          </div>

          {recentProfiles.length ? (
            <div className="recent-profile-grid">
            {recentProfiles.map((profile) => (
              <button
                type="button"
                className="recent-profile-card"
                key={profile.username}
                onClick={() => onOpenProfile(profile.username)}
              >
                <div className="recent-profile-avatar-wrap">
                  {profile.avatar_url ? (
                    <img
                      src={profile.avatar_url}
                      alt={copy.common.profileAvatarAlt({ username: profile.username })}
                      className="recent-profile-avatar"
                      loading="lazy"
                    />
                  ) : (
                    <div className="recent-profile-avatar fallback">
                      <Film size={20} />
                    </div>
                  )}
                </div>

                <div className="recent-profile-copy">
                  <strong>@{profile.username}</strong>
                  <span>{copy.home.recentProfileFollowers({ followers: profile.followers_abbr })}</span>
                  <span>{copy.home.recentProfileProcessed({ processed: profile.processed_count || 0, total: profile.reels_count || 0 })}</span>
                </div>
              </button>
            ))}
            </div>
          ) : (
            <p className="home-recent-empty">{copy.home.recentEmpty}</p>
          )}
      </section>

      <section className="home-section quiet">
        <div className="feature-quiet-grid">
          <div className="feature-quiet-item">
            <Mic size={24} />
            <h3>{copy.home.featureColumns[0].heading}</h3>
            <p>{copy.home.featureColumns[0].description}</p>
          </div>
          <div className="feature-quiet-item">
            <Sparkles size={24} />
            <h3>{copy.home.featureColumns[1].heading}</h3>
            <p>{copy.home.featureColumns[1].description}</p>
          </div>
          <div className="feature-quiet-item">
            <Download size={24} />
            <h3>{copy.home.featureColumns[2].heading}</h3>
            <p>{copy.home.featureColumns[2].description}</p>
          </div>
        </div>
      </section>
    </section>
  )
}

export function LoadingSkeleton() {
  return (
    <div className="skeleton-wrap" role="status" aria-label={copy.loading.profile}>
      <div className="skeleton-header">
        <div className="skeleton-avatar" />
        <div className="skeleton-header-copy">
          <div className="skeleton-line wide" />
          <div className="skeleton-line mid" />
          <div className="skeleton-pills">
            <div className="skeleton-pill" />
            <div className="skeleton-pill" />
            <div className="skeleton-pill" />
          </div>
        </div>
      </div>

      <div className="skeleton-grid">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="skeleton-card">
            <div className="skeleton-thumb" />
            <div className="skeleton-card-copy">
              <div className="skeleton-line wide" />
              <div className="skeleton-line short" />
              <div className="skeleton-line shorter" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function PrivateState() {
  return (
    <div className="state-card">
      <Lock size={48} />
      <h3>{copy.states.privateTitle}</h3>
      <p>{copy.states.privateSubtitle}</p>
    </div>
  )
}

export function ErrorState({ title, message, onRetry }) {
  return (
    <div className="state-card error">
      <AlertCircle size={48} />
      <h3>{title || copy.states.fetchFailedTitle}</h3>
      <p>{message || copy.states.fetchFailedSubtitle}</p>
      <button type="button" className="btn-secondary" onClick={onRetry}>{copy.states.fetchFailedButton}</button>
    </div>
  )
}

export function NoReelsState({ keyword = '', statusFilter = 'all' }) {
  const hasKeyword = Boolean(keyword.trim())
  const hasStatusOnly = statusFilter !== 'all'
  const normalizedStatus = statusFilter.replace('_', ' ').toLowerCase()

  const title = hasKeyword
    ? copy.states.noKeywordMatchTitle({ keyword })
    : hasStatusOnly
      ? copy.states.noStatusMatchTitle({ status: normalizedStatus })
      : copy.states.noReelsTitle

  const subtitle = hasKeyword
    ? copy.states.noKeywordMatchSubtitle
    : hasStatusOnly
      ? ''
      : copy.states.noReelsSubtitle

  return (
    <div className="state-card">
      <Film size={48} />
      <h3>{title}</h3>
      {subtitle ? <p>{subtitle}</p> : null}
    </div>
  )
}

export function SearchEmptyState() {
  return (
    <div className="state-card">
      <div className="empty-hero-icons small">
        <Film size={40} />
        <Search size={20} />
        <Sparkles size={20} />
      </div>
      <h3>{copy.states.startSearchTitle}</h3>
      <p>{copy.states.startSearchSubtitle}</p>
    </div>
  )
}
