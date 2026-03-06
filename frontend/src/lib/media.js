export const TRANSPARENT_PIXEL =
  'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='

export function resolveImageSrc(url) {
  if (!url) {
    return ''
  }

  if (!/^https?:\/\//i.test(url)) {
    return url
  }

  try {
    const host = new URL(url).hostname.toLowerCase()
    if (host.includes('res.cloudinary.com')) {
      return url
    }
    return `/proxy-image?url=${encodeURIComponent(url)}`
  } catch {
    return url
  }
}
