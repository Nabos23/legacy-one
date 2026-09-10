import { api } from './client'
import type {
  DbConnectionPublic,
  DbConnectionPreviewResponse,
  DbConnectionMetadataInput,
  DbConnectionTargetInput,
  Page,
} from '@/types'

export const dbConnectionsApi = {
  list: (page = 1, page_size = 10) =>
    api.get<Page<DbConnectionPublic>>(
      `/db-connections?page=${page}&page_size=${page_size}`
    ),
  listByOrg: (orgId: string, page = 1, page_size = 10) =>
    api.get<Page<DbConnectionPublic>>(
      `/organizations/${orgId}/db-connections?page=${page}&page_size=${page_size}`
    ),
  get: (id: string) => api.get<DbConnectionPublic>(`/db-connections/${id}`),
  preview: (body: { organization_id: string; connection_type?: string; name?: string } & DbConnectionTargetInput) =>
    api.post<DbConnectionPreviewResponse>('/db-connections/preview', body),
  create: (body: {
    organization_id: string
    table_descriptions?: Record<string, string>
  } & DbConnectionMetadataInput & DbConnectionTargetInput) => api.post<DbConnectionPublic>('/db-connections', body),
  update: (id: string, body: DbConnectionMetadataInput & DbConnectionTargetInput) =>
    api.put<DbConnectionPublic>(`/db-connections/${id}`, body),
  updateDescriptions: (id: string, body: { table_descriptions: Record<string, string> }) =>
    api.post<void>(`/db-connections/${id}/descriptions`, body),
  delete: (id: string) => api.delete<void>(`/db-connections/${id}`),
  getSchema: (id: string) => api.get<import('@/types').DbSchema>(`/db-connections/${id}/schema`),
  query: (id: string, body: { query: string }) =>
    api.post<{ result: string }>(`/db-connections/${id}/query`, body),
}
