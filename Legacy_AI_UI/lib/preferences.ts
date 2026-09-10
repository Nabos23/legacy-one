/** Small localStorage-backed personal preferences, shared across client + admin dashboards. */

const TIMEZONE_KEY = 'oneai:timezone'
const DENSITY_KEY = 'oneai:density'
const LANDING_KEY = 'oneai:default-landing'

export type Density = 'comfortable' | 'compact'

/** Fired on `window` whenever density changes, so the mounted dashboard shell can react without a reload. */
export const DENSITY_CHANGE_EVENT = 'oneai:density-change'

export function getStoredTimezone(): string {
  if (typeof window === 'undefined') return ''
  return localStorage.getItem(TIMEZONE_KEY) || ''
}

export function setStoredTimezone(tz: string) {
  if (typeof window === 'undefined') return
  if (tz) localStorage.setItem(TIMEZONE_KEY, tz)
  else localStorage.removeItem(TIMEZONE_KEY)
}

export function getStoredDensity(): Density {
  if (typeof window === 'undefined') return 'comfortable'
  return localStorage.getItem(DENSITY_KEY) === 'compact' ? 'compact' : 'comfortable'
}

export function setStoredDensity(density: Density) {
  if (typeof window === 'undefined') return
  localStorage.setItem(DENSITY_KEY, density)
  window.dispatchEvent(new CustomEvent<Density>(DENSITY_CHANGE_EVENT, { detail: density }))
}

/** Returns the stored default-landing sub-path if it's one of `validValues`, else null. */
export function getStoredLanding(validValues: readonly string[]): string | null {
  if (typeof window === 'undefined') return null
  const v = localStorage.getItem(LANDING_KEY)
  return v && validValues.includes(v) ? v : null
}

export function setStoredLanding(value: string) {
  if (typeof window === 'undefined') return
  localStorage.setItem(LANDING_KEY, value)
}

export const TIMEZONE_OPTIONS = [
  { value: '', label: 'Browser default' },
  { value: 'UTC', label: 'UTC' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (US)' },
  { value: 'America/Denver', label: 'Mountain Time (US)' },
  { value: 'America/Chicago', label: 'Central Time (US)' },
  { value: 'America/New_York', label: 'Eastern Time (US)' },
  { value: 'America/Sao_Paulo', label: 'São Paulo' },
  { value: 'Europe/London', label: 'London' },
  { value: 'Europe/Paris', label: 'Paris / Berlin' },
  { value: 'Europe/Moscow', label: 'Moscow' },
  { value: 'Africa/Cairo', label: 'Cairo' },
  { value: 'Asia/Dubai', label: 'Dubai' },
  { value: 'Asia/Karachi', label: 'Karachi' },
  { value: 'Asia/Kolkata', label: 'Mumbai / Delhi' },
  { value: 'Asia/Dhaka', label: 'Dhaka' },
  { value: 'Asia/Bangkok', label: 'Bangkok' },
  { value: 'Asia/Singapore', label: 'Singapore' },
  { value: 'Asia/Shanghai', label: 'Shanghai / Beijing' },
  { value: 'Asia/Tokyo', label: 'Tokyo' },
  { value: 'Australia/Sydney', label: 'Sydney' },
  { value: 'Pacific/Auckland', label: 'Auckland' },
] as const
