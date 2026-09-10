import { api } from './client'
import type {
  Page,
  PreviewQuestionsResponse,
  ScheduleCreate,
  SchedulePublic,
  ScheduleRunPublic,
  ScheduleUpdate,
} from '@/types'

export const schedulesApi = {
  previewQuestions: (target: string | { target_type?: 'agent' | 'orchestration'; agent_id?: string; orchestration_id?: string }, message: string) => {
    const payload = typeof target === 'string'
      ? { target_type: 'agent', agent_id: target, message }
      : {
          target_type: target.target_type || (target.orchestration_id ? 'orchestration' : 'agent'),
          agent_id: target.agent_id,
          orchestration_id: target.orchestration_id,
          message,
        }
    return api.post<PreviewQuestionsResponse>('/schedules/preview-questions', payload)
  },

  list: (params?: { needsAttention?: boolean; page?: number; pageSize?: number }) => {
    const qs = new URLSearchParams()
    if (params?.needsAttention !== undefined) qs.set('needs_attention', String(params.needsAttention))
    qs.set('page', String(params?.page ?? 1))
    qs.set('page_size', String(params?.pageSize ?? 50))
    return api.get<Page<SchedulePublic>>(`/schedules?${qs.toString()}`)
  },

  get: (id: string) => api.get<SchedulePublic>(`/schedules/${id}`),

  create: (body: ScheduleCreate) => api.post<SchedulePublic>('/schedules', body),

  update: (id: string, body: ScheduleUpdate) => api.patch<SchedulePublic>(`/schedules/${id}`, body),

  pause: (id: string) => api.post<SchedulePublic>(`/schedules/${id}/pause`, {}),

  resume: (id: string) => api.post<SchedulePublic>(`/schedules/${id}/resume`, {}),

  delete: (id: string) => api.delete<void>(`/schedules/${id}`),

  listRuns: (id: string, params?: { skip?: number; limit?: number }) => {
    const qs = new URLSearchParams()
    if (params?.skip !== undefined) qs.set('skip', String(params.skip))
    if (params?.limit !== undefined) qs.set('limit', String(params.limit))
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return api.get<ScheduleRunPublic[]>(`/schedules/${id}/runs${suffix}`)
  },
}
