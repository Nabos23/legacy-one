'use client'

import { useState } from 'react'
import { organizationsApi, authApi, type OrganizationSort } from '@/lib/api'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { OrganizationPublic, Page } from '@/types'

export function useOrganizations(
  initialPage = 1,
  search?: string,
  pageSize = 10,
  sort: OrganizationSort = {},
  isPublic = false,
) {
  const [page, setPage] = useState(initialPage)
  const { sortBy, sortOrder } = sort

  const { data, loading, error, refetch } = useApiQuery<Page<OrganizationPublic>>(
    queryKey('organizations', isPublic ? 'public' : 'private', page, search, pageSize, {
      sortBy,
      sortOrder,
    }),
    async () => {
      if (isPublic) {
        const result = await authApi.publicOrganizations()
        return {
          items: result,
          total: result.length,
          page: 1,
          page_size: result.length,
          total_pages: 1,
        }
      }
      const fetchPageSize = Math.min(pageSize, 100)
      const firstPage = await organizationsApi.list(page, fetchPageSize, search, { sortBy, sortOrder })
      if (pageSize > 100 && firstPage.total_pages > 1) {
        let allItems = [...firstPage.items]
        for (let p = 2; p <= firstPage.total_pages; p++) {
          const nextPage = await organizationsApi.list(p, 100, search, { sortBy, sortOrder })
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
  )

  return { data: data ?? null, loading, error, page, setPage, refetch }
}
