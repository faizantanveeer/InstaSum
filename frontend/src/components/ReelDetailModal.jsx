import { useEffect, useMemo, useState } from 'react'
import {
  AlignLeft,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Eye,
  FileText,
  Film,
  Heart,
  Play,
  X,
} from 'lucide-react'
import copy from '../copy'
import { formatCount, formatDate, formatDuration } from '../lib/format'
import { resolveImageSrc, TRANSPARENT_PIXEL } from '../lib/media'

export default function ReelDetailModal({ reels, index, open, onClose, onPrev, onNext, initialTab = 'summary' }) {
  const [tab, setTab] = useState(initialTab)
  const [imageFailed, setImageFailed] = useState(false)

  const reel = useMemo(() => {
    if (!open || index < 0 || index >= reels.length) return null
    return reels[index]
  }, [open, index, reels])

  useEffect(() => {
    if (open) {
      setTab(initialTab)
      setImageFailed(false)
    }
  }, [open, initialTab])

  useEffect(() => {
    if (!open) return undefined

    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowLeft') onPrev()
      if (event.key === 'ArrowRight') onNext()
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose, onPrev, onNext])

  if (!open || !reel) return null

  const thumbnailSrc = resolveImageSrc(reel.thumbnail_url)
  const showPlaceholder = !thumbnailSrc || imageFailed
  const transcriptText = reel.transcript
    ? reel.transcript.trim().toLowerCase().startsWith('no spoken content detected')
      ? copy.modal.transcriptNoSpeech
      : reel.transcript
    : copy.modal.transcriptPending

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="reel-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <button type="button" className="ghost-icon-btn modal-close" aria-label={copy.modal.close} onClick={onClose}>
          <X size={20} />
        </button>

        <button type="button" className="modal-nav prev" aria-label={copy.modal.previous} title={copy.modal.previous} onClick={onPrev}>
          <ChevronLeft size={20} />
        </button>
        <button type="button" className="modal-nav next" aria-label={copy.modal.next} title={copy.modal.next} onClick={onNext}>
          <ChevronRight size={20} />
        </button>

        <div className="modal-grid">
          <section className="modal-left">
            <div className="modal-thumb-frame">
              <img
                src={thumbnailSrc || TRANSPARENT_PIXEL}
                alt={reel.ai_title || copy.modal.imageAlt}
                className={`modal-thumb ${showPlaceholder ? 'is-hidden' : ''}`}
                loading="lazy"
                onError={() => setImageFailed(true)}
              />
              <div className={`modal-thumb placeholder ${showPlaceholder ? 'is-visible' : ''}`}>
                <Film size={24} />
              </div>
            </div>

            <div className="modal-left-actions">
              <a href={reel.reel_url} target="_blank" rel="noreferrer" className="btn-secondary">
                <ExternalLink size={16} />
                <span>{copy.modal.viewOnInstagram}</span>
              </a>
            </div>

            <div className="modal-meta-row">
              <span>{formatDate(reel.posted_at)}</span>
              <span><Heart size={16} /> {formatCount(reel.like_count)} {copy.modal.stats.likes}</span>
              <span><Eye size={16} /> {formatCount(reel.view_count)} {copy.modal.stats.views}</span>
              <span><Play size={16} /> {formatDuration(reel.video_duration)} {copy.modal.stats.duration}</span>
            </div>

            <p className="modal-audio-label">{copy.modal.audioLabel}</p>
            {reel.audio_url ? (
              <audio controls preload="none" src={reel.audio_url} className="modal-audio" />
            ) : (
              <div className="modal-audio-placeholder">{copy.modal.audioUnavailable}</div>
            )}
          </section>

          <section className="modal-right">
            <h2>{reel.ai_title || copy.modal.titleFallback}</h2>

            <div className="modal-tabs">
              <button
                type="button"
                className={`tab-btn ${tab === 'summary' ? 'active' : ''}`}
                onClick={() => setTab('summary')}
              >
                <FileText size={16} />
                <span>{copy.modal.tabs.summary}</span>
              </button>
              <button
                type="button"
                className={`tab-btn ${tab === 'transcript' ? 'active' : ''}`}
                onClick={() => setTab('transcript')}
              >
                <AlignLeft size={16} />
                <span>{copy.modal.tabs.transcript}</span>
              </button>
              <div className={`tab-underline ${tab}`} />
            </div>

            {tab === 'summary' ? (
              <div className="modal-content-text scroll-surface">
                {reel.summary_detail || reel.ai_summary || copy.modal.summaryPending}
              </div>
            ) : (
              <div className="modal-content-transcript scroll-surface">
                {transcriptText}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
