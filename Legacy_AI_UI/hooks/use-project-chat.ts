'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { projectsApi } from '@/lib/api'
import type { ChatMessage, LiveActivity } from '@/types'

interface UseProjectChatProps {
  projectId: string | null
}

export function useProjectChat({ projectId }: UseProjectChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [liveActivity, setLiveActivity] = useState<LiveActivity>(null)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  useEffect(() => () => abortRef.current?.abort(), [])

  // Fetch continuous project-based chat history from project_chats collection
  useEffect(() => {
    let mounted = true
    const loadHistory = async () => {
      setMessages([])
      setError(null)
      if (!projectId) {
        return
      }

      try {
        setIsTyping(true)
        const historyList = await projectsApi.getMessages(projectId)
        if (!mounted) return

        const allMessages: ChatMessage[] = historyList.map((m) => ({
          id: m.id,
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          timestamp: m.created_at,
          agent_id: m.project_id,
          auth_errors: m.auth_errors,
        }))

        setMessages(allMessages)
        setError(null)
      } catch (err: unknown) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Failed to load project history')
      } finally {
        if (mounted) setIsTyping(false)
      }
    }

    loadHistory()
    return () => {
      mounted = false
    }
  }, [projectId])

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || !projectId) return

      const userTimestamp = new Date().toISOString()
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: userTimestamp,
      }

      setMessages((prev) => [...prev, userMessage])
      setIsTyping(true)
      setLiveActivity(null)
      setError(null)

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      try {
        const stream = await projectsApi.streamChat(
          projectId,
          text,
          undefined,
          controller.signal,
        )

        let finalReply = ''
        let authErrors: any[] = []

        for await (const event of stream) {
          if (event.type === 'tool_call') {
            const p = event.payload || {}
            setLiveActivity({
              type: 'tool_call',
              kind: p.kind || 'tool',
              label: p.display_name || p.fn_name || 'tool',
            })
          } else if (event.type === 'done') {
            const p = event.payload || {}
            finalReply = p.reply || ''
            authErrors = p.auth_errors || []
          } else if (event.type === 'error') {
            throw new Error(event.payload?.message || 'Error occurred during chat turn.')
          }
        }

        const assistantMessage: ChatMessage = {
          id: `asst-${Date.now()}`,
          role: 'assistant',
          content: finalReply || 'Request completed.',
          timestamp: new Date().toISOString(),
          agent_id: projectId,
          auth_errors: authErrors.length ? authErrors : undefined,
        }

        setMessages((prev) => [...prev, assistantMessage])
      } catch (err: unknown) {
        if ((err as Error).name === 'AbortError') return
        const errorMessage = err instanceof Error ? err.message : 'Failed to send message'
        setError(errorMessage)
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content: `⚠️ Error: ${errorMessage}`,
            timestamp: new Date().toISOString(),
          },
        ])
      } finally {
        setIsTyping(false)
        setLiveActivity(null)
      }
    },
    [projectId],
  )

  const clearMessages = useCallback(async () => {
    if (projectId) {
      try {
        await projectsApi.clearMessages(projectId)
      } catch (err) {
        console.error('Failed to clear project messages in backend:', err)
      }
    }
    setMessages([])
    setError(null)
  }, [projectId])

  return {
    messages,
    isTyping,
    liveActivity,
    error,
    sendMessage,
    clearMessages,
  }
}
