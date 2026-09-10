import { api } from './client'
import type { ChatAttachmentResult } from './chat'
import type {
  OrchestrationPublic,
  OrchestrationCreate,
  OrchestrationUpdate,
  OrchestrationChatResponse,
  OrchestrationRunStatus,
  OrchestrationSessionHistoryResponse,
  OrchestrationSessionListResponse,
  OrchestrationInitResponse,
  Page,
} from '@/types'

export const orchestrationsApi = {
  init: (orchestrationId: string) =>
    api.post<OrchestrationChatResponse>(`/orchestrations/${orchestrationId}/chat`, { message: '' }),

  list: (page = 1, pageSize = 50) =>
    api.get<Page<OrchestrationPublic>>(`/orchestrations?page=${page}&page_size=${pageSize}`),

  get: (id: string) =>
    api.get<OrchestrationPublic>(`/orchestrations/${id}`),

  create: (body: OrchestrationCreate) =>
    api.post<OrchestrationPublic>('/orchestrations', body),

  update: (id: string, body: OrchestrationUpdate) =>
    api.patch<OrchestrationPublic>(`/orchestrations/${id}`, body),

  delete: (id: string) =>
    api.delete<void>(`/orchestrations/${id}`),

  chat: (orchestrationId: string, message: string, sessionId?: string, attachments?: ChatAttachmentResult[]) =>
    api.post<OrchestrationChatResponse>(`/orchestrations/${orchestrationId}/chat`, {
      message,
      session_id: sessionId,
      attachments: attachments?.length ? attachments : undefined,
    }),

  resume: (orchestrationId: string, runId: string, answer: string, branchId?: string) =>
    api.post<OrchestrationChatResponse>(`/orchestrations/${orchestrationId}/runs/${runId}/resume`, {
      answer,
      branch_id: branchId,
    }),

  runStatus: (orchestrationId: string, runId: string) =>
    api.get<OrchestrationRunStatus>(`/orchestrations/${orchestrationId}/runs/${runId}/status`),

  getSessionHistory: (orchestrationId: string, sessionId: string) =>
    api.get<OrchestrationSessionHistoryResponse>(
      `/orchestrations/${orchestrationId}/sessions/${sessionId}/history`),
  listSessions: (orchestrationId: string) =>
    api.get<OrchestrationSessionListResponse>(`/orchestrations/${orchestrationId}/sessions`),
  deleteSession: (orchestrationId: string, sessionId: string) =>
    api.delete<void>(`/orchestrations/${orchestrationId}/sessions/${sessionId}`),
  getBranchMessages: (orchestrationId: string, sessionId: string, branchId: string) =>
    api.get<OrchestrationSessionHistoryResponse>(
      `/orchestrations/${orchestrationId}/sessions/${sessionId}/branches/${branchId}/messages`),
}
