'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { chatApi } from '@/lib/api'
import type { ChatAttachmentResult } from '@/lib/api/chat'
import type { ChatMessage, ChatMessageHistory, LiveActivity } from '@/types'

interface UseChatProps {
  sessionId: string | null
  agentId: string | null
  orgId?: string
  onSessionCreated?: (sessionId: string) => void
  onSessionTitle?: (threadId: string, name: string) => void
}

function toolCallActivity(payload: any): LiveActivity {
  if (payload.kind === 'connector') {
    return { type: 'tool_call', kind: 'connector', label: payload.display_name }
  }
  if (payload.kind === 'tool' && payload.fn_name === 'search_schema') {
    return { type: 'tool_call', kind: 'tool', label: 'database schema' }
  }
  if (payload.kind === 'tool' && payload.fn_name === 'query_db') {
    return { type: 'tool_call', kind: 'tool', label: 'database' }
  }
  return null
}

export function useChat({ sessionId, agentId, orgId, onSessionCreated, onSessionTitle }: UseChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [liveActivity, setLiveActivity] = useState<LiveActivity>(null)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  useEffect(() => () => abortRef.current?.abort(), [])

  const currentSessionIdRef = useRef<string | null>(sessionId)
  const newlyCreatedSessionIdRef = useRef<string | null>(null)

  // Sync ref with props
  useEffect(() => {
    currentSessionIdRef.current = sessionId
  }, [sessionId])

  // Fetch history when session changes, or pre-warm Supervisor graph in RAM when on new session
  useEffect(() => {
    let mounted = true
    const loadHistory = async () => {
      if (!sessionId) {
        setMessages([])
        setError(null)
        // Pre-warm RAM cache for Supervisor session in background with loading signal
        if (!agentId) {
          setLiveActivity({ type: 'routing', agentId: 'supervisor', label: 'Initializing agents' })
          chatApi.createSession(orgId).then(session => {
            if (mounted && !currentSessionIdRef.current) {
              currentSessionIdRef.current = session.thread_id
              newlyCreatedSessionIdRef.current = session.thread_id
              if (onSessionCreated) onSessionCreated(session.thread_id)
            }
          }).finally(() => {
            if (mounted) setLiveActivity(null)
          })
        }
        return
      }

      if (sessionId === newlyCreatedSessionIdRef.current) {
        newlyCreatedSessionIdRef.current = null
        return
      }

      try {
        setIsTyping(true)
        const historyData = await chatApi.getSessionMessages(sessionId, orgId)
        if (!mounted) return

        const allMessages: ChatMessage[] = []
        
        historyData.agents?.forEach((agentHistory) => {
          agentHistory.conversations?.forEach((conv, i) => {
            if (conv.type === 'summary') {
              allMessages.push({
                id: `summary-${agentHistory.agent_id}-${i}-${conv.timestamp}`,
                role: 'assistant',
                content: `[Summary] ${conv.content}`,
                timestamp: conv.timestamp,
                agent_id: agentHistory.agent_id,
              })
            } else if (conv.type === 'turn') {
              allMessages.push({
                id: `human-${agentHistory.agent_id}-${i}-${conv.timestamp}`,
                role: 'user',
                content: conv.human_message,
                timestamp: conv.timestamp,
              })
              allMessages.push({
                id: `agent-${agentHistory.agent_id}-${i}-${conv.timestamp}`,
                role: 'assistant',
                content: conv.agent_message,
                timestamp: conv.timestamp,
                agent_id: agentHistory.agent_id,
                auth_errors: conv.auth_errors,
              })
            }
          })
        })

        allMessages.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

        const uniqueMessages: ChatMessage[] = []
        const seenUserMessages = new Set<string>()
        
        for (const msg of allMessages) {
          const formattedTimestamp = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          const formattedMsg = { ...msg, timestamp: formattedTimestamp }
          
          if (msg.role === 'user') {
            const key = `${msg.content}-${formattedTimestamp}`
            if (!seenUserMessages.has(key)) {
              seenUserMessages.add(key)
              uniqueMessages.push(formattedMsg)
            }
          } else {
            uniqueMessages.push(formattedMsg)
          }
        }

        setMessages(uniqueMessages)
        setError(null)
      } catch (e: unknown) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load history')
      } finally {
        if (mounted) setIsTyping(false)
      }
    }

    loadHistory()

    return () => {
      mounted = false
    }
  }, [sessionId, orgId])

  const send = useCallback(async (text: string, attachments?: ChatAttachmentResult[]) => {
    // Allow sending with attachments even if the typed text is empty (e.g. "summarize this doc").
    if (!text.trim() && !attachments?.length) return

    const payloadText = !agentId
      ? text
      : attachments?.length
        ? attachments
            .map(a => {
              if (a.kind === 'document' && a.text) {
                return `<attached_document name="${a.filename}">\n${a.text}\n</attached_document>`
              }
              if (a.kind === 'image') {
                const ocr = (a.ocr_text || '').trim()
                return ocr
                  ? `<attached_image name="${a.filename}">\n${ocr}\n</attached_image>`
                  : `<attached_image name="${a.filename}">\n[no OCR text extracted]\n</attached_image>`
              }
              return ''
            })
            .filter(Boolean)
            .join('\n\n') + (text.trim() ? `\n\n${text}` : '')
        : text

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      attachments: attachments?.map(a => a.filename),
    }
    setMessages(prev => [...prev, userMsg])

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setIsTyping(true)
    setLiveActivity(null)
    setError(null)

    try {
      if (agentId) {
        // Direct specific agent chat
        const stream = await chatApi.streamSendDirectMessage(
          agentId, payloadText, currentSessionIdRef.current || undefined, controller.signal
        )

        for await (const evt of stream) {
          if (evt.type === 'routing') {
            setLiveActivity({ type: 'routing', agentId: evt.payload.agent_id, label: evt.payload.agent_name })
          } else if (evt.type === 'tool_call') {
            setLiveActivity(toolCallActivity(evt.payload))
          } else if (evt.type === 'error') {
            setError(evt.payload.message)
          } else if (evt.type === 'done') {
            const res = evt.payload

            if (res.session_id && res.session_id !== currentSessionIdRef.current) {
              currentSessionIdRef.current = res.session_id
              newlyCreatedSessionIdRef.current = res.session_id
              if (onSessionCreated) onSessionCreated(res.session_id)
            }

            if (res.name && res.session_id && onSessionTitle) {
              onSessionTitle(res.session_id, res.name)
            }

            setMessages(prev => [
              ...prev,
              {
                id: `a-${Date.now()}`,
                role: 'assistant',
                content: res.reply,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                agent_id: agentId,
                trace_id: res.trace_id,
                auth_errors: res.auth_errors,
              },
            ])
          }
        }
      } else {
        // Non-specific session chat
        let activeThreadId = currentSessionIdRef.current
        if (!activeThreadId) {
          const session = await chatApi.createSession(orgId)
          activeThreadId = session.thread_id
          currentSessionIdRef.current = activeThreadId
          newlyCreatedSessionIdRef.current = activeThreadId
          if (onSessionCreated) onSessionCreated(activeThreadId)
        }

        const stream = await chatApi.streamSendMessage(
          activeThreadId,
          payloadText,
          orgId,
          controller.signal,
          attachments,
        )

        for await (const evt of stream) {
          if (evt.type === 'routing') {
            setLiveActivity({ type: 'routing', agentId: evt.payload.agent_id, label: evt.payload.agent_name })
          } else if (evt.type === 'tool_call') {
            setLiveActivity(toolCallActivity(evt.payload))
          } else if (evt.type === 'error') {
            setError(evt.payload.message)
          } else if (evt.type === 'done') {
            const res = evt.payload

            if (res.name && onSessionTitle) {
              onSessionTitle(activeThreadId, res.name)
            }

            setMessages(prev => [
              ...prev,
              {
                id: `a-${Date.now()}`,
                role: 'assistant',
                content: res.response,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                auth_errors: res.auth_errors,
              },
            ])
          }
        }
      }
    } catch (e: unknown) {
      if ((e as { name?: string })?.name !== 'AbortError') {
        setError(e instanceof Error ? e.message : 'Failed to send message')
      }
    } finally {
      setIsTyping(false)
      setLiveActivity(null)
    }
  }, [agentId, orgId, onSessionCreated, onSessionTitle])

  const reset = useCallback(() => {
    setMessages([])
    currentSessionIdRef.current = null
    setError(null)
  }, [])

  /** Remove a connector's auth-error banner from a message once it's been
   * reconnected — otherwise the banner stays stuck forever since it's only
   * ever set once, when the message first streams in. */
  const clearAuthError = useCallback((messageId: string, connectorId: string) => {
    setMessages(prev =>
      prev.map(m =>
        m.id === messageId && m.auth_errors
          ? { ...m, auth_errors: m.auth_errors.filter(e => e.connector_id !== connectorId) }
          : m
      )
    )
  }, [])

  return {
    messages,
    isTyping,
    liveActivity,
    error,
    send,
    reset,
    clearAuthError,
    sessionId: currentSessionIdRef.current,
  }
}
