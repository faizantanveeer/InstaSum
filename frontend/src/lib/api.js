import copy from '../copy'

const JSON_HEADERS = {
  'Content-Type': 'application/json',
}

export async function apiFetch(path, options = {}) {
  let response
  try {
    response = await fetch(path, {
      credentials: 'include',
      ...options,
      headers: {
        ...(options.body ? JSON_HEADERS : {}),
        ...(options.headers || {}),
      },
    })
  } catch {
    const error = new Error(copy.toasts.networkError)
    error.status = 0
    error.payload = null
    throw error
  }

  const contentType = response.headers.get('content-type') || ''
  let payload = null

  if (contentType.includes('application/json')) {
    payload = await response.json().catch(() => null)
  } else {
    const text = await response.text().catch(() => '')
    payload = text ? { message: text } : null
  }

  if (!response.ok) {
    const fallbackMessage = response.status === 401
      ? copy.toasts.sessionExpired
      : copy.errors.requestFailed({ status: response.status })
    const error = new Error(payload?.message || fallbackMessage)
    error.status = response.status
    error.payload = payload
    throw error
  }

  return payload
}
