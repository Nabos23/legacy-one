import { api } from './client'
import type {
  WidgetWebhookDeliveriesResponse,
  WidgetWebhookDeliveryResult,
  Page,
  SessionHistoryResponse,
  WidgetAnalytics,
  WidgetApiKeyResponse,
  WidgetConfigCreateInput,
  WidgetConfigPublic,
  WidgetConfigUpdateInput,
  WidgetImageUploadResponse,
  WidgetPreviewTokenResponse,
  WidgetSessionListItem,
  WidgetVersionListItem,
} from '@/types'

export const widgetsApi = {
  list: (page = 1, page_size = 20, organizationId?: string) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (organizationId) qs.set('organization_id', organizationId)
    return api.get<Page<WidgetConfigPublic>>(`/widget-configs?${qs.toString()}`)
  },
  get: (id: string) => api.get<WidgetConfigPublic>(`/widget-configs/${id}`),
  create: (body: WidgetConfigCreateInput) => api.post<WidgetConfigPublic>('/widget-configs', body),
  update: (id: string, body: WidgetConfigUpdateInput) =>
    api.put<WidgetConfigPublic>(`/widget-configs/${id}`, body),
  toggleStatus: (id: string, isEnabled: boolean) =>
    api.patch<WidgetConfigPublic>(`/widget-configs/${id}/status`, { is_enabled: isEnabled }),
  regenerateKey: (id: string) =>
    api.post<WidgetApiKeyResponse>(`/widget-configs/${id}/regenerate-key`, {}),
  delete: (id: string) => api.delete<void>(`/widget-configs/${id}`),
  duplicate: (id: string) => api.post<WidgetConfigPublic>(`/widget-configs/${id}/duplicate`, {}),
  createPreviewToken: (id: string) =>
    api.post<WidgetPreviewTokenResponse>(`/widget-configs/${id}/preview-token`, {}),
  publish: (id: string) => api.post<WidgetConfigPublic>(`/widget-configs/${id}/publish`, {}),
  discardDraft: (id: string) => api.post<WidgetConfigPublic>(`/widget-configs/${id}/discard-draft`, {}),
  getVersions: (id: string, page = 1, page_size = 20) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    return api.get<Page<WidgetVersionListItem>>(`/widget-configs/${id}/versions?${qs.toString()}`)
  },
  rollback: (id: string, version: number) =>
    api.post<WidgetConfigPublic>(`/widget-configs/${id}/versions/${version}/rollback`, {}),
  uploadImage: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<WidgetImageUploadResponse>(`/widget-configs/${id}/upload-image`, form)
  },
  getSessions: (id: string, page = 1, page_size = 20) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    return api.get<Page<WidgetSessionListItem>>(`/widget-configs/${id}/sessions?${qs.toString()}`)
  },
  getSessionHistory: (id: string, visitorSessionId: string) =>
    api.get<SessionHistoryResponse>(`/widget-configs/${id}/sessions/${visitorSessionId}/history`),
  getAnalytics: (id: string) => api.get<WidgetAnalytics>(`/widget-configs/${id}/analytics`),
  testWebhook: (id: string, event: string) =>
    api.post<WidgetWebhookDeliveryResult>(`/widget-configs/${id}/webhooks/${event}/test`, {}),
  replayWebhookDelivery: (id: string, deliveryId: string) =>
    api.post<WidgetWebhookDeliveryResult>(`/widget-configs/${id}/webhook-deliveries/${deliveryId}/replay`, {}),
  getWebhookDeliveries: (id: string, page = 1, pageSize = 20) =>
    api.get<WidgetWebhookDeliveriesResponse>(`/widget-configs/${id}/webhook-deliveries?page=${page}&page_size=${pageSize}`),
}
