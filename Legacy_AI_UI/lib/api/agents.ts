import { api } from './client'
import type { AgentAvatarType, AgentPublic, Page, AgentPermissionsDoc, AgentPermissionsPatch } from '@/types'

export interface AgentListFilters {
  isActive?: boolean
  hasTools?: boolean
  hasConnectors?: boolean
  hasMcp?: boolean
  sortBy?: 'name' | 'created_at' | 'is_active'
  sortOrder?: 'asc' | 'desc'
}

function appendAgentFilters(qs: URLSearchParams, f?: AgentListFilters) {
  if (!f) return
  if (f.isActive !== undefined) qs.set('is_active', String(f.isActive))
  if (f.hasTools !== undefined) qs.set('has_tools', String(f.hasTools))
  if (f.hasConnectors !== undefined) qs.set('has_connectors', String(f.hasConnectors))
  if (f.hasMcp !== undefined) qs.set('has_mcp', String(f.hasMcp))
  if (f.sortBy) qs.set('sort_by', f.sortBy)
  if (f.sortOrder) qs.set('sort_order', f.sortOrder)
}

export const agentsApi = {
  list: (page = 1, page_size = 10, search?: string, filters?: AgentListFilters, organizationId?: string) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (search) qs.set('search', search)
    if (organizationId) qs.set('organization_id', organizationId)
    appendAgentFilters(qs, filters)
    return api.get<Page<AgentPublic>>(`/agents?${qs.toString()}`)
  },
  listByOrg: (orgId: string, page = 1, page_size = 10, search?: string, filters?: AgentListFilters) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (search) qs.set('search', search)
    appendAgentFilters(qs, filters)
    return api.get<Page<AgentPublic>>(`/organizations/${orgId}/agents?${qs.toString()}`)
  },
  get: (id: string) => api.get<AgentPublic>(`/agents/${id}`),
  create: (body: {
    organization_id: string
    name: string
    prompt: string
    guardrails: string
    description?: string
    tool_ids?: string[]
    mcp_server_ids?: string[]
    connector_ids?: string[]
    avatar_type?: AgentAvatarType
    avatar_value?: string | null
    owner_scope?: 'user' | 'organization' | 'selected_users' | 'team'
    allowed_user_ids?: string[]
    team_id?: string
  }) => api.post<AgentPublic>('/agents', body),
  update: (id: string, body: Partial<AgentPublic> & {
    avatar_type?: AgentAvatarType
    avatar_value?: string | null
  }) =>
    api.put<AgentPublic>(`/agents/${id}`, body),
  uploadAvatar: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<AgentPublic>(`/agents/${id}/avatar`, form)
  },
  toggleStatus: (id: string, isActive: boolean) =>
    api.patch<AgentPublic>(`/agents/${id}/status`, { is_active: isActive }),
  delete: (id: string) => api.delete<void>(`/agents/${id}`),
  getPermissions: (id: string) => api.get<AgentPermissionsDoc>(`/agents/${id}/permissions`),
  patchPermissions: (id: string, body: AgentPermissionsPatch) =>
    api.patch<AgentPermissionsDoc>(`/agents/${id}/permissions`, body),
}

