'use client'

import { useCallback, useState } from 'react'
import { agentsApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { AgentPublic, Page } from '@/types'

export interface UseAgentsFilters {
  isActive?: boolean
  hasTools?: boolean
  hasConnectors?: boolean
  hasMcp?: boolean
  sortBy?: 'name' | 'created_at' | 'is_active'
  sortOrder?: 'asc' | 'desc'
}

export function useAgents(
  initialPage = 1,
  explicitOrgId?: string,
  search?: string,
  pageSize = 10,
  filters: UseAgentsFilters = {},
) {
  const { user, permissions, loading: authLoading } = useAuth()
  const orgId = explicitOrgId ?? (permissions?.is_super_admin ? undefined : user?.organization_id)
  const { isActive, hasTools, hasConnectors, hasMcp, sortBy, sortOrder } = filters

  const [page, setPage] = useState(initialPage)

  const apiFilters = { isActive, hasTools, hasConnectors, hasMcp, sortBy, sortOrder }

  const ready = !authLoading || !!explicitOrgId

  const { data, loading, error, refetch, mutate } = useApiQuery<Page<AgentPublic>>(
    queryKey('agents', page, orgId, search, pageSize, apiFilters),
    () =>
      orgId
        ? agentsApi.listByOrg(orgId, page, pageSize, search, apiFilters)
        : agentsApi.list(page, pageSize, search, apiFilters),
    { enabled: ready },
  )

  const updateLocal = useCallback(
    (id: string, patch: Partial<AgentPublic>) => {
      mutate(prev =>
        prev ? { ...prev, items: prev.items.map(a => (a.id === id ? { ...a, ...patch } : a)) } : prev,
      )
    },
    [mutate],
  )

  return {
    data: data ?? null,
    loading: loading || !ready,
    error,
    page,
    setPage,
    refetch,
    updateLocal,
  }
}
