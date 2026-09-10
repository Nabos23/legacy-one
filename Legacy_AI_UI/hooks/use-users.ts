'use client'

import { useState } from 'react'
import { usersApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { UserPublic, Page } from '@/types'

export interface UseUsersSort {
  sortBy?: 'name' | 'email' | 'created_at'
  sortOrder?: 'asc' | 'desc'
}

export function useUsers(
  initialPage = 1,
  explicitOrgId?: string,
  search?: string,
  role?: string,
  pageSize = 10,
  sort: UseUsersSort = {},
  enabled = true,
) {
  const { user, permissions, loading: authLoading } = useAuth()
  const orgId = explicitOrgId ?? (permissions?.is_super_admin ? undefined : user?.organization_id)
  const { sortBy, sortOrder } = sort

  const [page, setPage] = useState(initialPage)

  const ready = enabled && (!authLoading || !!explicitOrgId)

  const { data, loading, error, refetch } = useApiQuery<Page<UserPublic>>(
    queryKey('users', page, orgId, search, role, pageSize, { sortBy, sortOrder }),
    async () => {
      const fetchPageSize = Math.min(pageSize, 100)
      const firstPage = orgId
        ? await usersApi.listByOrg(orgId, page, fetchPageSize, search, role, { sortBy, sortOrder })
        : await usersApi.list(page, fetchPageSize, search, role, { sortBy, sortOrder })
      if (pageSize > 100 && firstPage.total_pages > 1) {
        let allItems = [...firstPage.items]
        for (let p = 2; p <= firstPage.total_pages; p++) {
          const nextPage = orgId
            ? await usersApi.listByOrg(orgId, p, 100, search, role, { sortBy, sortOrder })
            : await usersApi.list(p, 100, search, role, { sortBy, sortOrder })
          allItems = allItems.concat(nextPage.items)
        }
        return {
          ...firstPage,
          items: allItems,
          page_size: allItems.length,
          total_pages: 1,
        }
      }
      return firstPage
    },
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
