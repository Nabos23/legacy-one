import { api } from './client'
import type { ToolRegistryPublic, Page } from '@/types'

export interface ToolRegistryListFilters {
  search?: string
  type?: string
  isActive?: boolean
  sortBy?: 'name' | 'created_at'
  sortOrder?: 'asc' | 'desc'
}

export const toolRegistryApi = {
  list: (page = 1, page_size = 20, filters: ToolRegistryListFilters = {}) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (filters.search) qs.set('search', filters.search)
    if (filters.type) qs.set('type', filters.type)
    if (filters.isActive !== undefined) qs.set('is_active', String(filters.isActive))
    if (filters.sortBy) qs.set('sort_by', filters.sortBy)
    if (filters.sortOrder) qs.set('sort_order', filters.sortOrder)
    return api.get<Page<ToolRegistryPublic>>(`/tool-registry?${qs.toString()}`)
  },
  get: (id: string) => api.get<ToolRegistryPublic>(`/tool-registry/${id}`),
  create: (body: {
    name: string
    type: 'db' | 'db_query' | 'http' | 'rag' | 'custom' | string
    description?: string
    is_active?: boolean
    tool_schema?: Record<string, unknown>
  }) => api.post<ToolRegistryPublic>('/tool-registry', body),
  update: (id: string, body: Partial<ToolRegistryPublic>) =>
    api.put<ToolRegistryPublic>(`/tool-registry/${id}`, body),
  delete: (id: string) => api.delete<void>(`/tool-registry/${id}`),
}
