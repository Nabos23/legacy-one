'use client'

import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react'
import {
  DEFAULT_TTL_MS,
  fetchQuery,
  hasBeenAttempted,
  isFresh,
  mutateQuery,
  queryKey,
  readQuery,
  subscribeQuery,
  type QuerySnapshot,
} from '@/lib/api/query-cache'

export { queryKey }

export interface UseApiQueryOptions {
  ttlMs?: number
  enabled?: boolean
}

export interface UseApiQueryResult<T> {
  data: T | undefined
  loading: boolean
  error: string | null
  validating: boolean
  refetch: () => Promise<void>
  mutate: (updater: (prev: T | undefined) => T | undefined) => void
}

export function useApiQuery<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  options: UseApiQueryOptions = {},
): UseApiQueryResult<T> {
  const { ttlMs = DEFAULT_TTL_MS, enabled = true } = options
  const active = enabled && key !== null
  const cacheKey = active ? key! : ''

  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const pendingFirstLoad = active && !hasBeenAttempted(cacheKey)

  const snapshot = useSyncExternalStore<QuerySnapshot<T>>(
    useCallback(
      onChange => (active ? subscribeQuery(cacheKey, onChange) : () => {}),
      [active, cacheKey],
    ),
    useCallback(() => readSnapshot<T>(cacheKey, active), [cacheKey, active]),
    getServerSnapshot,
  )

  useEffect(() => {
    if (!active) return
    if (isFresh(cacheKey, ttlMs)) return
    fetchQuery(cacheKey, () => fetcherRef.current()).catch(() => {})
  }, [active, cacheKey, ttlMs])

  const refetch = useCallback(async () => {
    if (!active) return
    try {
      await fetchQuery(cacheKey, () => fetcherRef.current())
    } catch {
      /* empty */
    }
  }, [active, cacheKey])

  const mutate = useCallback(
    (updater: (prev: T | undefined) => T | undefined) => {
      if (active) mutateQuery<T>(cacheKey, updater)
    },
    [active, cacheKey],
  )

  return {
    data: snapshot.data,
    loading: active && (snapshot.loading || (pendingFirstLoad && !snapshot.validating)),
    error: snapshot.error,
    validating: snapshot.validating,
    refetch,
    mutate,
  }
}

const INERT: QuerySnapshot<never> = { data: undefined, error: null, loading: false, validating: false }

function getServerSnapshot<T>(): QuerySnapshot<T> {
  return INERT as QuerySnapshot<T>
}

function readSnapshot<T>(key: string, active: boolean): QuerySnapshot<T> {
  return active ? readQuery<T>(key) : (INERT as QuerySnapshot<T>)
}
