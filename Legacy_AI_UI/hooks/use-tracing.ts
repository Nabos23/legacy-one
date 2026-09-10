'use client'

import { useMemo } from 'react'
import { tracingApi } from '@/lib/api'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { TracePublic, TraceStats, Page } from '@/types'

const TRACE_TTL_MS = 15_000

export const RECENT_TRACES_PAGE_SIZE = 100

export function useTracing(page = 1, agentId?: string) {
  const { data, loading, error, refetch } = useApiQuery<Page<TracePublic>>(
    queryKey('traces', page, agentId),
    () => tracingApi.listTraces({ page, agent_id: agentId }),
    { ttlMs: TRACE_TTL_MS },
  )
  return { data: data ?? null, loading, error, refetch }
}

export function useRecentTraces(orgId?: string, enabled = true) {
  const { data, loading, error, refetch } = useApiQuery<Page<TracePublic>>(
    queryKey('traces:recent', RECENT_TRACES_PAGE_SIZE, orgId),
    () => tracingApi.listTraces({ page: 1, page_size: RECENT_TRACES_PAGE_SIZE, org_id: orgId }),
    { ttlMs: TRACE_TTL_MS, enabled },
  )
  const traces = useMemo(() => data?.items ?? EMPTY_TRACES, [data])
  return { traces, loading, error, refetch }
}

const EMPTY_TRACES: TracePublic[] = []

export function useTraceStats(agentId?: string, orgId?: string, userId?: string) {
  const { data, loading } = useApiQuery<TraceStats>(
    queryKey('traces:stats', agentId, orgId, userId),
    () => tracingApi.getStats(agentId, orgId, userId),
    { ttlMs: TRACE_TTL_MS },
  )
  return { stats: data ?? null, loading }
}

export interface TraceListFilters {
  page?: number
  agentId?: string
  sessionId?: string
  userId?: string
  orgId?: string
}

export function useTraceList(filters: TraceListFilters, enabled = true) {
  const { page = 1, agentId, sessionId, userId, orgId } = filters
  const { data, loading, error, refetch } = useApiQuery<Page<TracePublic>>(
    queryKey('traces:list', page, agentId, sessionId, userId, orgId),
    () =>
      tracingApi.listTraces({
        page,
        agent_id: agentId || undefined,
        session_id: sessionId || undefined,
        user_id: userId || undefined,
        org_id: orgId,
      }),
    { ttlMs: TRACE_TTL_MS, enabled },
  )
  return { data: data ?? null, loading, error, refetch }
}
