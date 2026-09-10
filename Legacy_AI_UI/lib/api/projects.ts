import { api, ApiError, getAuthHeaders, handleUnauthorized } from './client'
import { API_BASE_URL } from '@/lib/config'
import type {
  Page,
  ProjectCreateInput,
  ProjectFilePublic,
  ProjectPublic,
  ProjectUpdateInput,
  ProjectChatMessagePublic,
  ProjectChatResponse,
} from '@/types'
import type { ChatStreamEvent } from './chat'

export interface ProjectListFilters {
  hasTools?: boolean
  hasConnectors?: boolean
  hasMcp?: boolean
  sortBy?: 'name' | 'created_at'
  sortOrder?: 'asc' | 'desc'
}

function appendProjectFilters(qs: URLSearchParams, f?: ProjectListFilters) {
  if (!f) return
  if (f.hasTools !== undefined) qs.set('has_tools', String(f.hasTools))
  if (f.hasConnectors !== undefined) qs.set('has_connectors', String(f.hasConnectors))
  if (f.hasMcp !== undefined) qs.set('has_mcp', String(f.hasMcp))
  if (f.sortBy) qs.set('sort_by', f.sortBy)
  if (f.sortOrder) qs.set('sort_order', f.sortOrder)
}

async function* parseSSE(res: Response): AsyncGenerator<ChatStreamEvent> {
  if (res.status === 401) {
    handleUnauthorized()
    throw new ApiError(401, 'Unauthorized')
  }
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const line = raw.split('\n').find((l) => l.startsWith('data:'))
      if (line) yield JSON.parse(line.slice(5).trim())
    }
  }
}

export const projectsApi = {
  list: (page = 1, page_size = 20, search?: string, filters?: ProjectListFilters, organizationId?: string) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (search) qs.set('search', search)
    if (organizationId) qs.set('organization_id', organizationId)
    appendProjectFilters(qs, filters)
    return api.get<Page<ProjectPublic>>(`/projects?${qs.toString()}`)
  },
  listByOrg: (orgId: string, page = 1, page_size = 20, search?: string, filters?: ProjectListFilters) => {
    const qs = new URLSearchParams({ page: String(page), page_size: String(page_size) })
    if (search) qs.set('search', search)
    appendProjectFilters(qs, filters)
    return api.get<Page<ProjectPublic>>(`/projects?organization_id=${orgId}&${qs.toString()}`)
  },
  get: (id: string) => api.get<ProjectPublic>(`/projects/${id}`),
  create: (body: ProjectCreateInput) => api.post<ProjectPublic>('/projects', body),
  update: (id: string, body: ProjectUpdateInput) => api.patch<ProjectPublic>(`/projects/${id}`, body),
  delete: (id: string) => api.delete<void>(`/projects/${id}`),
  uploadFile: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<ProjectFilePublic>(`/projects/${projectId}/files`, form)
  },
  listFiles: (projectId: string) => api.get<ProjectFilePublic[]>(`/projects/${projectId}/files`),
  getFile: (projectId: string, fileId: string) => api.get<ProjectFilePublic>(`/projects/${projectId}/files/${fileId}`),
  deleteFile: (projectId: string, fileId: string) => api.delete<void>(`/projects/${projectId}/files/${fileId}`),
  getMessages: (projectId: string, limit = 100) =>
    api.get<ProjectChatMessagePublic[]>(`/projects/${projectId}/messages?limit=${limit}`),
  clearMessages: (projectId: string) =>
    api.delete<void>(`/projects/${projectId}/messages`),
  chat: (projectId: string, message: string, sessionId?: string) =>
    api.post<ProjectChatResponse>(`/projects/${projectId}/chat`, {
      message,
      session_id: sessionId,
    }),
  streamChat: async (projectId: string, message: string, sessionId?: string, signal?: AbortSignal) => {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal,
    })
    return parseSSE(res)
  },
}
