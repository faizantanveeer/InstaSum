import copy from '../copy'

export function formatCount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return copy.profile.statFallback
  const n = Number(value)
  if (Math.abs(n) >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1).replace(/\.0$/, '')}B`
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`
  return `${Math.trunc(n)}`
}

export function formatDate(isoString) {
  if (!isoString) return copy.profile.statFallback
  const dt = new Date(isoString)
  if (Number.isNaN(dt.getTime())) return isoString
  return dt.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return '--:--'
  const total = Math.max(0, Math.round(Number(seconds)))
  const m = Math.floor(total / 60)
  const s = `${total % 60}`.padStart(2, '0')
  return `${m}:${s}`
}
