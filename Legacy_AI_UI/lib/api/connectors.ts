import { api, withRetry } from './client'
import type {
  ConnectorAuthUrlResponse,
  ConnectorCredentialsSave,
  ConnectorRegistryItem,
  ConnectorRegistryPage,
  ConnectorSetupInfo,
  ConnectorStatus,
  ConnectorTestConnectionResult,
} from '@/types/connectors'

export interface RegistryAdminParams {
  page?: number
  page_size?: number
  q?: string
  category?: string
  sortBy?: 'name' | 'category'
  sortOrder?: 'asc' | 'desc'
}

export const connectorsApi = {
  getRegistry(): Promise<ConnectorRegistryItem[]> {
    return api.get('/api/connectors/registry')
  },

  getRegistryAdmin(params: RegistryAdminParams = {}): Promise<ConnectorRegistryPage> {
    const qs = new URLSearchParams()
    if (params.page)      qs.set('page', String(params.page))
    if (params.page_size) qs.set('page_size', String(params.page_size))
    if (params.q)         qs.set('q', params.q)
    if (params.category)  qs.set('category', params.category)
    if (params.sortBy)    qs.set('sort_by', params.sortBy)
    if (params.sortOrder) qs.set('sort_order', params.sortOrder)
    const query = qs.toString()
    return api.get(`/api/connectors/registry/admin${query ? `?${query}` : ''}`)
  },

  setVisibility(connectorId: string, isVisible: boolean): Promise<ConnectorRegistryItem> {
    return api.patch(`/api/connectors/registry/${connectorId}/visibility`, { is_visible: isVisible })
  },

  getSetupInfo(connectorId: string): Promise<ConnectorSetupInfo> {
    return api.get(`/api/connectors/${connectorId}/setup`)
  },

  configure(connectorId: string, data: ConnectorCredentialsSave): Promise<{ message: string }> {
    return api.post(`/api/connectors/${connectorId}/configure`, data)
  },

  deleteCredentials(connectorId: string): Promise<{ message: string }> {
    return api.delete(`/api/connectors/${connectorId}/configure`)
  },

  getAuthUrl(connectorId: string): Promise<ConnectorAuthUrlResponse> {
    return api.get(`/api/connectors/${connectorId}/auth-url`)
  },

  getStatus(connectorId: string): Promise<ConnectorStatus> {
    return withRetry(() => api.get(`/api/connectors/${connectorId}/status`))
  },

  disconnect(connectorId: string): Promise<{ message: string }> {
    return api.post(`/api/connectors/${connectorId}/disconnect`, {})
  },

  testConnection(connectorId: string): Promise<ConnectorTestConnectionResult> {
    return withRetry(() => api.post(`/api/connectors/${connectorId}/test-connection`, {}))
  },

  runAction(connectorId: string, action: string, params?: Record<string, unknown>): Promise<unknown> {
    return api.post(`/api/connectors/${connectorId}/actions/${action}`, params ?? {})
  },
}
