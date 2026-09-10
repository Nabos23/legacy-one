'use client'

import { toolRegistryApi, type ToolRegistryListFilters } from '@/lib/api'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { ToolRegistryPublic, Page } from '@/types'

export function useToolRegistry(page = 1, pageSize = 50, filters: ToolRegistryListFilters = {}) {
  const { search, type, isActive, sortBy, sortOrder } = filters

  const { data, loading, error, refetch } = useApiQuery<Page<ToolRegistryPublic>>(
    queryKey('tool-registry', page, pageSize, { search, type, isActive, sortBy, sortOrder }),
    () => toolRegistryApi.list(page, pageSize, { search, type, isActive, sortBy, sortOrder }),
  )

  return { data: data ?? null, loading, error, refetch }
}
