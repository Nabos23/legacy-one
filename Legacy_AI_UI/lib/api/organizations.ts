import { api } from './client'
import type { OrganizationPublic, Page } from '@/types'

export interface OrganizationSort {
  sortBy?: 'name' | 'created_at'
  sortOrder?: 'asc' | 'desc'
}

export const organizationsApi = {
  list: (page = 1, page_size = 10, search?: string, sort?: OrganizationSort) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (search) qs.set('search', search)
    if (sort?.sortBy) qs.set('sort_by', sort.sortBy)
    if (sort?.sortOrder) qs.set('sort_order', sort.sortOrder)
    return api.get<Page<OrganizationPublic>>(`/organizations?${qs.toString()}`)
  },
  get: (id: string) => api.get<OrganizationPublic>(`/organizations/${id}`),
  create: (body: { name: string; description?: string }) =>
    api.post<OrganizationPublic>('/organizations', body),
  update: (id: string, body: Partial<OrganizationPublic>) =>
    api.put<OrganizationPublic>(`/organizations/${id}`, body),
  delete: (id: string) => api.delete<void>(`/organizations/${id}`),
}
