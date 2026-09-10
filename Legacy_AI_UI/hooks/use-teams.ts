'use client'

import { useState } from 'react'
import { teamsApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { TeamPublic, Page } from '@/types'

export function useTeams(
  initialPage = 1,
  explicitOrgId?: string,
  search?: string,
  pageSize = 10,
  enabled = true,
) {
  const { user, permissions, loading: authLoading } = useAuth()
  const orgId = explicitOrgId ?? (permissions?.is_super_admin ? undefined : user?.organization_id)

  const [page, setPage] = useState(initialPage)

  const ready = enabled && (!authLoading || !!explicitOrgId)

  const { data, loading, error, refetch } = useApiQuery<Page<TeamPublic>>(
    queryKey('teams', page, orgId, search, pageSize),
    () =>
      orgId
        ? teamsApi.listByOrg(orgId, page, pageSize, search)
        : teamsApi.list(page, pageSize, search),
    { enabled: ready },
  )

  return {
    data: data ?? null,
    loading: enabled ? loading || !ready : false,
    error,
    page,
    setPage,
    refetch,
  }
}
