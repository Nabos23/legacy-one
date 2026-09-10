import { api } from './client'
import type { ToolPublic, Page } from '@/types'

export interface ToolCredentialsPayload {
  api_key?: string
  base_url?: string
  model?: string
}

export const toolsApi = {
  list: (page = 1, page_size = 10) =>
    api.get<Page<ToolPublic>>(`/tools?page=${page}&page_size=${page_size}`),
  listByOrg: (orgId: string, page = 1, page_size = 10) =>
    api.get<Page<ToolPublic>>(`/organizations/${orgId}/tools?page=${page}&page_size=${page_size}`),
  get: (id: string) => api.get<ToolPublic>(`/tools/${id}`),
  create: (body: {
    organization_id: string
    agent_id: string
    user_description: string
    tool_id: string
    name?: string
    db_conn_id?: string
    credentials?: ToolCredentialsPayload
    enabled?: boolean
  }) => api.post<ToolPublic>('/tools', body),
  update: (id: string, body: {
    name?: string
    user_description?: string
    tool_id?: string
    db_conn_id?: string
    credentials?: ToolCredentialsPayload
  }) =>
    api.put<ToolPublic>(`/tools/${id}`, body),
  delete: (id: string) => api.delete<void>(`/tools/${id}`),
}