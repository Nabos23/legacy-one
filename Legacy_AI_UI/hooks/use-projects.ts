'use client'

import { useState, useEffect, useCallback } from 'react'
import { projectsApi, type ProjectListFilters } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import type { ProjectPublic, Page } from '@/types'

export interface UseProjectsFilters extends ProjectListFilters {}

export function useProjects(
  initialPage = 1,
  explicitOrgId?: string,
  search?: string,
  pageSize = 20,
  filters: UseProjectsFilters = {},
) {
  const { user, permissions } = useAuth()
  const orgId = explicitOrgId ?? (permissions?.is_super_admin ? undefined : user?.organization_id)
  const { hasTools, hasConnectors, hasMcp, sortBy, sortOrder } = filters

  const [data, setData] = useState<Page<ProjectPublic> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(initialPage)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const apiFilters = { hasTools, hasConnectors, hasMcp, sortBy, sortOrder }
      const result = orgId
        ? await projectsApi.listByOrg(orgId, page, pageSize, search, apiFilters)
        : await projectsApi.list(page, pageSize, search, apiFilters)
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load projects')
    } finally {
      setLoading(false)
    }
  }, [page, orgId, search, pageSize, hasTools, hasConnectors, hasMcp, sortBy, sortOrder])

  useEffect(() => {
    fetch()
  }, [fetch])

  const updateLocal = useCallback((id: string, patch: Partial<ProjectPublic>) => {
    setData((prev) =>
      prev ? { ...prev, items: prev.items.map((p) => (p.id === id ? { ...p, ...patch } : p)) } : prev,
    )
  }, [])

  const removeLocal = useCallback((id: string) => {
    setData((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.filter((p) => p.id !== id),
            total: Math.max(0, prev.total - 1),
          }
        : prev,
    )
  }, [])

  return { data, loading, error, page, setPage, refetch: fetch, updateLocal, removeLocal }
}
