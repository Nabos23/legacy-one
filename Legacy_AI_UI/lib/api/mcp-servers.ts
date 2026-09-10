import { api } from './client'
import type { McpServerPublic, McpAgentToolPublic, McpCatalogEntry, McpToolSpec, McpTestConnectionResult, Page } from '@/types'

export interface McpCreatePayload {
  organization_id: string
  agent_id?: string
  registry_key?: string
  connection_string?: string
  placeholders?: Record<string, string>
  name?: string
  user_description?: string
  token?: string
  headers?: Record<string, string>
  timeout?: number
}

export interface McpUpdatePayload {
  name?: string
  user_description?: string
  connection_string?: string
  token?: string
  headers?: Record<string, string>
  timeout?: number
  is_active?: boolean
}

export interface McpTestPayload {
  connection_string: string
  token?: string
  headers?: Record<string, string>
  timeout?: number
}

export interface McpOAuthStartPayload {
  organization_id: string
  agent_id?: string
  connection_string: string
  name?: string
  user_description?: string
  scope?: string
}

export interface McpOAuthStartResponse {
  authorization_url: string
  state: string
}

export const mcpApi = {
  list: (page = 1, page_size = 20, search?: string, status?: string, agentId?: string) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (search) qs.set('search', search)
    if (status) qs.set('status', status)
    if (agentId) qs.set('agent_id', agentId)
    return api.get<Page<McpServerPublic>>(`/mcp-servers?${qs.toString()}`)
  },

  listByAgent: (agentId: string, page = 1) =>
    api.get<Page<McpServerPublic>>(`/mcp-servers/agent/${agentId}?page=${page}`),

  get: (id: string) =>
    api.get<McpServerPublic>(`/mcp-servers/${id}`),

  catalog: (q?: string) =>
    api.get<McpCatalogEntry[]>(`/mcp-servers/catalog${q ? `?q=${encodeURIComponent(q)}` : ''}`),

  testConnection: (payload: McpTestPayload) =>
    api.post<McpTestConnectionResult>('/mcp-servers/test-connection', payload),

  create: (payload: McpCreatePayload) =>
    api.post<McpServerPublic>('/mcp-servers', payload),

  oauthStart: (payload: McpOAuthStartPayload) =>
    api.post<McpOAuthStartResponse>('/mcp-servers/oauth/start', payload),

  discover: (id: string) =>
    api.post<McpServerPublic>(`/mcp-servers/${id}/discover`, {}),

  update: (id: string, payload: McpUpdatePayload) =>
    api.put<McpServerPublic>(`/mcp-servers/${id}`, payload),

  delete: (id: string) =>
    api.delete<void>(`/mcp-servers/${id}`),

  // Per-tool attachment — a server's individual tools attached to an agent,
  // independent of the legacy whole-server `agent_id` above.
  serverTools: (serverId: string) =>
    api.get<McpToolSpec[]>(`/mcp-servers/${serverId}/tools`),

  attachTools: (serverId: string, agentId: string, toolNames: string[]) =>
    api.post<McpAgentToolPublic[]>(`/mcp-servers/${serverId}/agents/${agentId}/tools`, { tool_names: toolNames }),

  detachTool: (serverId: string, agentId: string, toolName: string) =>
    api.delete<void>(`/mcp-servers/${serverId}/agents/${agentId}/tools/${encodeURIComponent(toolName)}`),

  toolAgents: (serverId: string, toolName: string, page = 1) =>
    api.get<Page<McpAgentToolPublic>>(`/mcp-servers/${serverId}/tools/${encodeURIComponent(toolName)}/agents?page=${page}`),

  agentTools: (agentId: string, page = 1, page_size = 20) =>
    api.get<Page<McpAgentToolPublic>>(`/mcp-servers/agent/${agentId}/tools?page=${page}&page_size=${page_size}`),
}
