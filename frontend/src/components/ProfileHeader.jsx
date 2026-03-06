import { useMemo, useState } from 'react'
import {
  Download,
  FileJson,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import copy from '../copy'
import { resolveImageSrc } from '../lib/media'

function statChip(label, value) {
  return (
    <div className="stat-chip" key={label}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export default function ProfileHeader({
  profile,
  refreshing,
  onRefresh,
  onExport,
  unprocessedCount,
  onGenerateAll,
  generateAllState,
}) {
  const [showBioFull, setShowBioFull] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showGenerateConfirm, setShowGenerateConfirm] = useState(false)

  const hasLongBio = (profile?.biography || '').length > 140
  const displayBio = useMemo(() => {
    if (showBioFull || !hasLongBio) return profile?.biography || ''
    return `${(profile?.biography || '').slice(0, 140)}...`
  }, [profile?.biography, hasLongBio, showBioFull])

  const estimateLabel = copy.profile.timeEstimate({ reels: unprocessedCount })
  const followersValue = profile?.followers_abbr || copy.profile.statFallback
  const followingValue = profile?.following_abbr || copy.profile.statFallback
  const reelsValue = `${profile?.processed_count || 0}/${profile?.reels_count || 0}`
  const generateLabel = generateAllState?.running
    ? copy.profile.generateAllProgress({
      n: generateAllState.processed || 0,
      total: generateAllState.total || 0,
    })
    : !unprocessedCount
      ? copy.profile.generateAllDone
      : copy.profile.generateAll

  return (
    <header className="profile-header-react">
      <div className="profile-left">
        <div className="profile-avatar-ring">
          {profile?.profile_pic_url ? (
            <img src={resolveImageSrc(profile.profile_pic_url)} alt={copy.common.profileAvatarAlt({ username: profile.username })} loading="lazy" />
          ) : (
            <div className="profile-avatar-placeholder">@{(profile?.username || '?').slice(0, 1).toUpperCase()}</div>
          )}
        </div>

        <div className="profile-meta">
          <h1>@{profile?.username}</h1>
          <p className="display-name">{profile?.full_name || profile?.username}</p>
          {profile?.biography ? (
            <p className="profile-bio">
              {displayBio}{' '}
              {hasLongBio ? (
                <button type="button" className="link-btn" onClick={() => setShowBioFull((v) => !v)}>
                  {showBioFull ? copy.profile.readLess : copy.profile.readMore}
                </button>
              ) : null}
            </p>
          ) : null}

          <div className="profile-stats-row">
            {statChip(copy.profile.statLabels.followers, followersValue)}
            {statChip(copy.profile.statLabels.following, followingValue)}
            {statChip(copy.profile.statLabels.reels, reelsValue)}
          </div>
        </div>
      </div>

      <div className="profile-actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={onRefresh}
          disabled={refreshing || generateAllState?.running}
          title={refreshing ? copy.profile.refreshLoadingTooltip : copy.profile.refreshTooltip}
        >
          <RefreshCw size={20} className={refreshing ? 'spin' : ''} />
          <span>{copy.profile.refreshLabel}</span>
        </button>

        <div className="popover-wrap">
          <button type="button" className="btn-secondary" onClick={() => setShowExport((v) => !v)} title={copy.profile.exportLabel}>
            <Download size={20} />
            <span>{copy.profile.exportLabel}</span>
          </button>
          {showExport ? (
            <div className="popover-menu">
              <button type="button" onClick={() => { setShowExport(false); onExport('csv') }}>
                <FileText size={16} />
                <span>{copy.profile.exportCsv}</span>
              </button>
              <button type="button" onClick={() => { setShowExport(false); onExport('json') }}>
                <FileJson size={16} />
                <span>{copy.profile.exportJson}</span>
              </button>
            </div>
          ) : null}
        </div>

        <div className="popover-wrap">
          <button
            type="button"
            className="btn-primary"
            onClick={() => setShowGenerateConfirm((v) => !v)}
            disabled={generateAllState?.running || !unprocessedCount}
          >
            {generateAllState?.running ? <Loader2 size={20} className="spin" /> : <Sparkles size={20} />}
            <span>{generateLabel}</span>
          </button>

          {showGenerateConfirm ? (
            <div className="popover-menu generate-confirm">
              <p>{copy.profile.generateConfirmHeading({ n: unprocessedCount })}</p>
              <p>{copy.profile.generateConfirmSubtext({ estimate: estimateLabel })}</p>
              <div className="confirm-actions">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => {
                    setShowGenerateConfirm(false)
                    onGenerateAll(false)
                  }}
                >
                  {copy.profile.startGenerating}
                </button>
                <button type="button" className="btn-secondary" onClick={() => setShowGenerateConfirm(false)}>
                  {copy.profile.cancel}
                </button>
              </div>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setShowGenerateConfirm(false)
                  onGenerateAll(true)
                }}
              >
                {copy.profile.regenerateAll}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  )
}
