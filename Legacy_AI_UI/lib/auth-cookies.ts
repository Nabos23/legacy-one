import { getStoredLanding } from './preferences'

const AUTH_COOKIE = 'access_token'

// SECURITY NOTE: This cookie is written from JavaScript (document.cookie) so it
// CANNOT be HttpOnly — that flag can only be set by the server via Set-Cookie.
// It exists solely so the Next.js edge middleware can gate routes server-side.
// The hardening we can apply client-side: Secure (HTTPS only) + SameSite=Strict.
// The full fix (an HttpOnly, server-set session cookie) requires the backend to
// issue the cookie on login — tracked separately.
function cookieAttrs(maxAge: number) {
  const secure = typeof window !== 'undefined' && window.location.protocol === 'https:'
  return `path=/; max-age=${maxAge}; SameSite=Strict${secure ? '; Secure' : ''}`
}

export function setAuthCookie(token: string, rememberMe = false, role?: string, permissions?: Record<string, boolean>) {
  const maxAge = rememberMe ? 2592000 : 86400 // 30 days or 24 hours
  document.cookie = `${AUTH_COOKIE}=${token}; ${cookieAttrs(maxAge)}`
  if (role) {
    document.cookie = `user_role=${role}; ${cookieAttrs(maxAge)}`
  }
  if (permissions) {
    const activePerms = Object.entries(permissions)
      .filter(([, value]) => Boolean(value))
      .map(([key]) => key)
    document.cookie = `user_permissions=${encodeURIComponent(activePerms.join(','))}; ${cookieAttrs(maxAge)}`
  }
}

export function clearAuthCookie() {
  document.cookie = `${AUTH_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; ${cookieAttrs(0)}`
  document.cookie = `user_role=; expires=Thu, 01 Jan 1970 00:00:00 GMT; ${cookieAttrs(0)}`
  document.cookie = `user_permissions=; expires=Thu, 01 Jan 1970 00:00:00 GMT; ${cookieAttrs(0)}`
}

export const CLIENT_LANDING_PATHS = ['dashboard', 'agents', 'playground', 'tracing'] as const
export const ADMIN_LANDING_PATHS = ['dashboard', 'organizations', 'agents', 'playground', 'tracing'] as const

export function getDashboardPath(role: string) {
  const isAdmin = role === 'super_admin' || role === 'super admin'
  const base = isAdmin ? '/admin' : '/client'
  const validPaths = isAdmin ? ADMIN_LANDING_PATHS : CLIENT_LANDING_PATHS
  const stored = getStoredLanding(validPaths)
  return `${base}/${stored ?? 'dashboard'}`
}
