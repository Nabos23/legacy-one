import { api, ApiError, getAuthHeaders, handleUnauthorized } from './client'
import { API_BASE_URL } from '@/lib/config'
import type { ChatResponse, SessionChatResponse, DirectChatResponse } from '@/types'

export interface ChatStreamEvent {
  type: 'routing' | 'tool_call' | 'done' | 'error'
  payload: any
}

/** Processed chat attachment from POST /chat/attachments. */
export interface ChatAttachmentResult {
  kind: 'document' | 'image'
  filename: string
  // document
  text?: string
  chars?: number
  truncated?: boolean
  // image
  mime?: string
  data_url?: string
  ocr_text?: string
}

/** @deprecated Use ChatAttachmentResult — kept for any leftover callers. */
export type ExtractedDocument = ChatAttachmentResult

/** Parses a `text/event-stream` response body (one `data: <json>` line per
 * event, blank-line terminated) into a stream of typed events. Raw `fetch` +
 * manual parsing is used instead of `EventSource` because these endpoints
 * are POST requests with an auth header and a JSON body, neither of which
 * `EventSource` supports. */
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
      const line = raw.split('\n').find(l => l.startsWith('data:'))
      if (line) yield JSON.parse(line.slice(5).trim())
    }
  }
}

export const chatApi = {
  createSession: (orgId?: string) =>
    api.post<import('@/types').SessionPublic>(`/chat/session${orgId ? `?organization_id=${orgId}` : ''}`, {}),
  sendMessage: (threadId: string, message: string, orgId?: string, attachments?: ChatAttachmentResult[]) =>
    api.post<SessionChatResponse>('/chat/message', {
      thread_id: threadId,
      message,
      organization_id: orgId,
      attachments: attachments?.length ? attachments : undefined,
    }),
  sendDirectMessage: (agentId: string, message: string, sessionId?: string) =>
    api.post<DirectChatResponse>('/chat', {
      agent_id: agentId,
      message,
      session_id: sessionId,
    }),
  streamSendMessage: async (
    threadId: string,
    message: string,
    orgId: string | undefined,
    signal?: AbortSignal,
    attachments?: ChatAttachmentResult[],
  ) => {
    const res = await fetch(`${API_BASE_URL}/chat/message/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({
        thread_id: threadId,
        message,
        organization_id: orgId,
        attachments: attachments?.length ? attachments : undefined,
      }),
      signal,
    })
    return parseSSE(res)
  },
  streamSendDirectMessage: async (agentId: string, message: string, sessionId: string | undefined, signal?: AbortSignal) => {
    const res = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ agent_id: agentId, message, session_id: sessionId }),
      signal,
    })
    return parseSSE(res)
  },
  listSessions: (orgId?: string, agentId?: string) => {
    const params = new URLSearchParams()
    if (orgId) params.set('organization_id', orgId)
    if (agentId) params.set('agent_id', agentId)
    const q = params.toString()
    return api.get<import('@/types').ChatSessionHistory[]>(`/chat/sessions${q ? `?${q}` : ''}`)
  },
  renameSession: (threadId: string, name: string) =>
    api.patch<import('@/types').ChatSessionHistory>(`/chat/sessions/${threadId}`, { name }),
  deleteSession: (threadId: string) =>
    api.delete(`/chat/sessions/${threadId}`),
  getSessionMessages: (sessionId: string, orgId?: string) =>
    api.get<import('@/types').SessionHistoryResponse>(`/chat/sessions/${sessionId}/history${orgId ? `?organization_id=${orgId}` : ''}`),
  /** Process a chat attachment (document → text, or image → data URL + OCR).
   * The file is not stored — the caller attaches the result to the next message.
   * `onProgress` (0-100) reflects the upload only, not server-side extraction/OCR time. */
  processAttachment: (file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData()
    form.append('file', file)
    return api.postFormWithProgress<ChatAttachmentResult>('/chat/attachments', form, onProgress)
  },
  /** @deprecated Prefer processAttachment */
  extractDocument: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.postForm<ChatAttachmentResult>('/chat/attachments', form)
  },
}
