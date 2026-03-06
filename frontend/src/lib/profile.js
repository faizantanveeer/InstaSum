export function normalizeProfileInput(value = '') {
  const raw = value.trim()
  if (!raw) {
    return ''
  }

  let candidate = raw

  if (/^https?:\/\//i.test(raw)) {
    try {
      const url = new URL(raw)
      const parts = url.pathname.split('/').filter(Boolean)
      if (['reel', 'p', 'tv', 'stories'].includes((parts[0] || '').toLowerCase())) {
        return ''
      }
      candidate = parts[0] || ''
    } catch {
      candidate = raw
    }
  }

  candidate = candidate
    .replace(/^@+/, '')
    .replace(/^instagram\.com\//i, '')
    .replace(/\/+$/, '')

  if (candidate.includes('/')) {
    candidate = candidate.split('/').filter(Boolean)[0] || candidate
  }

  return candidate.toLowerCase()
}
