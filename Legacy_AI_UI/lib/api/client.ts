import { API_BASE_URL } from '@/lib/config'

const BASE_URL = API_BASE_URL

/** Fired on any 403 response so a shared UI (the dashboard layout's "Access Denied"
 * screen) can react without every caller having to check `err.status === 403` itself. */
export const API_FORBIDDEN_EVENT = 'api:forbidden'

const notifyForbidden = () => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(API_FORBIDDEN_EVENT))
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: any
  ) {
    const message = Array.isArray(detail)
      ? detail.map(d => d.msg || JSON.stringify(d)).join(', ')
      : typeof detail === 'string'
        ? detail
        : String(detail);
    super(message)
    this.name = 'ApiError'
  }
}

const getToken = () =>
  typeof window === 'undefined' ? null : localStorage.getItem('access_token')

/** Bearer auth header, reused by callers (like SSE streaming) that need a raw
 * `fetch` instead of the JSON-only `apiRequest` wrapper below. */
export const getAuthHeaders = (): Record<string, string> => {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Shared 401 handling, reused by raw-`fetch` callers that can't go through `apiRequest`. */
export const handleUnauthorized = () => {
  localStorage.removeItem('access_token')
  if (typeof window !== 'undefined') {
    document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax;'
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }
}

async function apiRequest<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const token = getToken()
  // FormData bodies must NOT get a manual Content-Type — the browser sets one
  // itself (including the multipart boundary) only when the header is absent.
  const isFormData = init?.body instanceof FormData
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (res.status === 401) {
    handleUnauthorized()
    throw new ApiError(401, 'Unauthorized')
  }

  if (res.status === 403) {
    notifyForbidden()
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(403, body.detail ?? res.statusText)
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }

  // 204 No Content (and other empty bodies, e.g. DELETE) have nothing to parse.
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  const token = getToken()

  const normalizedPath = path.startsWith('http://') || path.startsWith('https://')
    ? path
    : path.replace(/\/+/g, '/')

  const targetUrl = normalizedPath.startsWith('http://') || normalizedPath.startsWith('https://')
    ? normalizedPath
    : `${BASE_URL}${normalizedPath.startsWith('/') ? '' : '/'}${normalizedPath}`

  const res = await fetch(targetUrl, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (res.status === 401) {
    localStorage.removeItem('access_token')
    if (typeof window !== 'undefined') {
      document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax;'
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    throw new ApiError(401, 'Unauthorized')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }

  const blob = await res.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(blobUrl)
}

export async function apiFetchBlobUrl(path: string): Promise<string> {
  const token = getToken()

  const normalizedPath = path.startsWith('http://') || path.startsWith('https://')
    ? path
    : path.replace(/\/+/g, '/')

  const targetUrl = normalizedPath.startsWith('http://') || normalizedPath.startsWith('https://')
    ? normalizedPath
    : `${BASE_URL}${normalizedPath.startsWith('/') ? '' : '/'}${normalizedPath}`

  const res = await fetch(targetUrl, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (res.status === 401) {
    handleUnauthorized()
    throw new ApiError(401, 'Unauthorized')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }

  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

/**
 * Multipart upload with real upload-progress events — `fetch` has no
 * `onprogress` equivalent, so this one call goes through `XMLHttpRequest`
 * instead of `apiRequest`. Same auth/401/error-shape handling as the rest of
 * `api.*`, just reimplemented for XHR's callback API.
 */
function postFormWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress?: (percent: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE_URL}${path}`)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status === 401) {
        handleUnauthorized()
        reject(new ApiError(401, 'Unauthorized'))
        return
      }
      const body = xhr.responseText ? JSON.parse(xhr.responseText) : undefined
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T)
      } else {
        reject(new ApiError(xhr.status, body?.detail ?? xhr.statusText))
      }
    }
    xhr.onerror = () => reject(new ApiError(0, 'Network error'))
    xhr.send(formData)
  })
}

export const api = {
  get: <T,>(p: string) => apiRequest<T>(p),
  post: <T,>(p: string, b: unknown) =>
    apiRequest<T>(p, { method: 'POST', body: JSON.stringify(b) }),
  put: <T,>(p: string, b: unknown) =>
    apiRequest<T>(p, { method: 'PUT', body: JSON.stringify(b) }),
  patch: <T,>(p: string, b: unknown) =>
    apiRequest<T>(p, { method: 'PATCH', body: JSON.stringify(b) }),
  delete: <T,>(p: string) => apiRequest<T>(p, { method: 'DELETE' }),
  /** Multipart upload — the browser sets its own Content-Type (with boundary) for FormData. */
  postForm: <T,>(p: string, formData: FormData) =>
    apiRequest<T>(p, { method: 'POST', body: formData }),
  /** Multipart upload that reports real upload progress via `onProgress(percent)`. */
  postFormWithProgress,
}

const RETRY_MAX_ATTEMPTS = 3
const RETRY_BASE_DELAY_MS = 300

const isRetryable = (err: unknown): boolean =>
  err instanceof ApiError ? err.status === 429 || err.status >= 500 : true

/**
 * Retries a read call with exponential backoff + jitter, but only for
 * failures that look transient (429/5xx or a network-level error) —
 * a definitive 4xx is a real answer, not a blip, and is rethrown immediately.
 * Kept separate from `apiRequest`/`api.*` so mutations never get silently
 * retried.
 */
export async function withRetry<T>(fn: () => Promise<T>, maxAttempts = RETRY_MAX_ATTEMPTS): Promise<T> {
  let lastErr: unknown
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastErr = err
      if (!isRetryable(err) || attempt === maxAttempts) throw err
      const delay = RETRY_BASE_DELAY_MS * 2 ** (attempt - 1)
      await new Promise(resolve => setTimeout(resolve, delay + Math.random() * delay * 0.25))
    }
  }
  throw lastErr
}
