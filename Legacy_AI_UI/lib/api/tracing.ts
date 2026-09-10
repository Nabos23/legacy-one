import { api } from './client'
import type { TracePublic, TraceDetail, TraceStats, SessionPublic, Page } from '@/types'

export const tracingApi = {
  listTraces: (params?: {
    agent_id?: string
    session_id?: string
    user_id?: string
    page?: number
    page_size?: number
    org_id?: string
  }) => {
    const p = { page: '1', page_size: '20', ...Object.fromEntries(
      Object.entries(params ?? {})
        .filter(([, v]) => v != null)
        .map(([k, v]) => [k === 'org_id' ? 'organization_id' : k, String(v)])
    ) }
    return api.get<Page<TracePublic>>(`/traces?${new URLSearchParams(p)}`)
  },
  getTrace: (id: string, org_id?: string) =>
    api.get<TraceDetail>(`/traces/${id}${org_id ? `?organization_id=${org_id}` : ''}`),
  getStats: (agent_id?: string, org_id?: string, user_id?: string) => {
    const params = new URLSearchParams()
    if (agent_id) params.set('agent_id', agent_id)
    if (org_id) params.set('organization_id', org_id)
    if (user_id) params.set('user_id', user_id)
    const qs = params.toString()
    return api.get<TraceStats>(`/traces/stats${qs ? `?${qs}` : ''}`)
  },
  listSessions: (page = 1, page_size = 20) =>
    api.get<Page<SessionPublic>>(`/sessions?page=${page}&page_size=${page_size}`),
  agentTraces: (agent_id: string, page = 1) =>
    api.get<Page<TracePublic>>(`/agents/${agent_id}/traces?page=${page}`),
  agentStats: (agent_id: string) =>
    api.get<TraceStats>(`/agents/${agent_id}/stats`),
}
