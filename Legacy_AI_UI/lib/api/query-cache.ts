export const DEFAULT_TTL_MS = 5_000

interface CacheEntry<T = unknown> {
  data: T | undefined
  error: string | null
  fetchedAt: number
  promise: Promise<T> | null
  listeners: Set<() => void>
  snapshot: QuerySnapshot<T> | null
}

const cache = new Map<string, CacheEntry>()

const MAX_ENTRIES = 200

function evictIfNeeded() {
  if (cache.size <= MAX_ENTRIES) return
  const evictable = [...cache.entries()]
    .filter(([, e]) => e.listeners.size === 0 && !e.promise)
    .sort((a, b) => a[1].fetchedAt - b[1].fetchedAt)
  for (const [key] of evictable.slice(0, cache.size - MAX_ENTRIES)) {
    cache.delete(key)
  }
}

function getEntry<T>(key: string): CacheEntry<T> {
  let entry = cache.get(key) as CacheEntry<T> | undefined
  if (!entry) {
    entry = {
      data: undefined,
      error: null,
      fetchedAt: 0,
      promise: null,
      listeners: new Set(),
      snapshot: null,
    }
    cache.set(key, entry as CacheEntry)
    evictIfNeeded()
  }
  return entry
}

function notify(entry: CacheEntry) {
  entry.listeners.forEach(l => l())
}

export function queryKey(name: string, ...params: unknown[]): string {
  const parts = params.map(p => {
    if (p == null) return ''
    if (typeof p === 'object') {
      const obj = p as Record<string, unknown>
      return JSON.stringify(
        Object.keys(obj)
          .filter(k => obj[k] !== undefined)
          .sort()
          .reduce<Record<string, unknown>>((acc, k) => ((acc[k] = obj[k]), acc), {}),
      )
    }
    return String(p)
  })
  return `${name}(${parts.join('|')})`
}

export interface QuerySnapshot<T> {
  data: T | undefined
  error: string | null
  loading: boolean
  validating: boolean
}

const EMPTY_SNAPSHOT: QuerySnapshot<never> = {
  data: undefined,
  error: null,
  loading: false,
  validating: false,
}

export function readQuery<T>(key: string): QuerySnapshot<T> {
  const entry = cache.get(key) as CacheEntry<T> | undefined
  if (!entry) return EMPTY_SNAPSHOT as QuerySnapshot<T>
  const next: QuerySnapshot<T> = {
    data: entry.data,
    error: entry.error,
    loading: !!entry.promise && entry.data === undefined,
    validating: !!entry.promise,
  }
  const prev = entry.snapshot
  if (
    prev &&
    prev.data === next.data &&
    prev.error === next.error &&
    prev.loading === next.loading &&
    prev.validating === next.validating
  ) {
    return prev
  }
  entry.snapshot = next
  return next
}

export function isFresh(key: string, ttlMs = DEFAULT_TTL_MS): boolean {
  const entry = cache.get(key)
  return !!entry && entry.data !== undefined && Date.now() - entry.fetchedAt < ttlMs
}

export function hasData(key: string): boolean {
  const entry = cache.get(key)
  return !!entry && entry.data !== undefined
}

export function hasBeenAttempted(key: string): boolean {
  const entry = cache.get(key)
  return !!entry && (entry.fetchedAt > 0 || entry.error !== null || entry.promise !== null)
}

export function subscribeQuery(key: string, listener: () => void): () => void {
  const entry = getEntry(key)
  entry.listeners.add(listener)
  return () => {
    entry.listeners.delete(listener)
  }
}

export function fetchQuery<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const entry = getEntry<T>(key)
  if (entry.promise) return entry.promise

  const promise = fetcher()
    .then(result => {
      entry.data = result
      entry.error = null
      entry.fetchedAt = Date.now()
      return result
    })
    .catch((e: unknown) => {
      entry.error = e instanceof Error ? e.message : 'Request failed'
      throw e
    })
    .finally(() => {
      entry.promise = null
      notify(entry as CacheEntry)
    })

  entry.promise = promise
  notify(entry as CacheEntry)
  return promise
}

export function mutateQuery<T>(key: string, updater: (prev: T | undefined) => T | undefined): void {
  const entry = getEntry<T>(key)
  entry.data = updater(entry.data)
  notify(entry as CacheEntry)
}

export function invalidateQueries(prefix: string): void {
  for (const [key, entry] of cache) {
    if (key === prefix || key.startsWith(`${prefix}(`)) {
      entry.fetchedAt = 0
      notify(entry)
    }
  }
}

export function clearQueryCache(): void {
  cache.clear()
}
