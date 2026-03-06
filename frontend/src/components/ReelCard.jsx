import { memo, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle,
  Eye,
  Film,
  Heart,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
} from 'lucide-react'
import copy from '../copy'
import { formatCount, formatDate, formatDuration } from '../lib/format'
import { resolveImageSrc, TRANSPARENT_PIXEL } from '../lib/media'

function ReelCardComponent({ reel, onOpen, onGenerate, onRegenerate, viewMode, isBusy }) {
  const status = reel.processing_status || 'pending'
  const hasTitle = Boolean((reel.ai_title || '').trim())
  const [imageFailed, setImageFailed] = useState(false)

  const thumbnailSrc = useMemo(() => resolveImageSrc(reel.thumbnail_url), [reel.thumbnail_url])
  const summaryText = reel.ai_summary || reel.summary_detail || copy.card.summaryPending

  useEffect(() => {
    setImageFailed(false)
  }, [thumbnailSrc])

  let StatusIcon = null
  let statusLabel = copy.card.status.pending
  if (status === 'completed') StatusIcon = CheckCircle
  if (status === 'completed') statusLabel = copy.card.status.completed
  if (status === 'processing') {
    StatusIcon = Loader2
    statusLabel = copy.card.status.processing
  }
  if (status === 'failed') {
    StatusIcon = AlertCircle
    statusLabel = copy.card.status.failed
  }

  const cardClass = viewMode === 'list' ? 'reel-card list' : 'reel-card'
  const showPlaceholder = !thumbnailSrc || imageFailed

  return (
    <article className={cardClass} data-reel-id={reel.id}>
      <div className="reel-thumb-wrap">
        <img
          src={thumbnailSrc || TRANSPARENT_PIXEL}
          alt={reel.ai_title || copy.modal.imageAlt}
          className={`reel-thumb ${showPlaceholder ? 'is-hidden' : ''}`}
          loading="lazy"
          onError={() => setImageFailed(true)}
        />
        <div className={`reel-thumb placeholder ${showPlaceholder ? 'is-visible' : ''}`}>
          <Film size={24} />
        </div>

        <span className="duration-pill">{formatDuration(reel.video_duration)}</span>

        {StatusIcon ? (
          <span className={`status-pill status-${status}`} title={statusLabel}>
            <StatusIcon size={16} className={status === 'processing' ? 'spin' : ''} />
            <span>{statusLabel}</span>
          </span>
        ) : null}

        <div className="thumb-overlay">
          <button type="button" className="icon-overlay-btn" onClick={() => onOpen(reel, 'audio')} aria-label={copy.card.playAudio} title={copy.card.playAudio}>
            <Play size={20} />
          </button>
          <button
            type="button"
            className="icon-overlay-btn"
            onClick={() => onGenerate(reel.id)}
            aria-label={copy.card.generate}
            title={copy.card.generate}
            disabled={isBusy}
          >
            <Sparkles size={20} />
          </button>
          <button type="button" className="icon-overlay-btn" onClick={() => onOpen(reel)} aria-label={copy.card.viewDetails} title={copy.card.viewDetails}>
            <Eye size={20} />
          </button>
        </div>
      </div>

      <div className="reel-card-body">
        <div className="reel-card-copy">
          <h3 className={`reel-card-title ${!hasTitle ? 'skeleton-title' : ''}`}>
            {hasTitle ? reel.ai_title : copy.card.notGenerated}
          </h3>

          <div className="reel-summary-scroll scroll-surface">
            <p className={`reel-summary-text ${status !== 'completed' ? 'is-muted' : ''}`}>{summaryText}</p>
            {status === 'failed' && reel.error_reason ? <div className="reel-error-text">{reel.error_reason}</div> : null}
          </div>
        </div>

        <div className="reel-card-footer">
          <div className="reel-card-actions">
            <button type="button" className="ghost-inline-btn" onClick={() => onOpen(reel, 'audio')}>
              <Play size={16} />
              <span>{copy.card.playAudio}</span>
            </button>
            <button type="button" className="ghost-inline-btn" onClick={() => onGenerate(reel.id)} disabled={isBusy}>
              {isBusy ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
              <span>{isBusy ? copy.card.running : copy.card.generate}</span>
            </button>
            <button type="button" className="ghost-inline-btn" onClick={() => onRegenerate(reel.id)} disabled={isBusy}>
              <RotateCcw size={16} />
              <span>{copy.card.regenerate}</span>
            </button>
          </div>

          <div className="reel-card-meta">
            <span>{formatDate(reel.posted_at)}</span>
            <span><Heart size={16} /> {formatCount(reel.like_count)}</span>
            <span><Eye size={16} /> {formatCount(reel.view_count)}</span>
          </div>
        </div>
      </div>
    </article>
  )
}

const ReelCard = memo(ReelCardComponent)

export default ReelCard
