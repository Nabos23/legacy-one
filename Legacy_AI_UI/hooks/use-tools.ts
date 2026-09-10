'use client'

import { useState } from 'react'
import { toolsApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { ToolPublic, Page } from '@/types'

export function useTools(initialPage = 1, explicitOrgId?: string, pageSize = 10) {
  const { user, permissions, loading: authLoading } = useAuth()
  const orgId = explicitOrgId ?? (permissions?.is_super_admin ? undefined : user?.organization_id)

  const [page, setPage] = useState(initialPage)

  const ready = !authLoading || !!explicitOrgId

  const { data, loading, error, refetch } = useApiQuery<Page<ToolPublic>>(
    queryKey('tools', page, orgId, pageSize),
    () => (orgId ? toolsApi.listByOrg(orgId, page, pageSize) : toolsApi.list(page, pageSize)),
    { enabled: ready },
  )

  return { data: data ?? null, loading: loading || !ready, error, page, setPage, refetch }
}
