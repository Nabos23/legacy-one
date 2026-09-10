'use client'

import { useCallback, useMemo } from 'react'
import { chatApi } from '@/lib/api'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { ChatSessionHistory } from '@/types'

const EMPTY: ChatSessionHistory[] = []

export function useSessions(orgId?: string, agentId?: string) {
  const { data, loading, error, refetch, mutate } = useApiQuery<ChatSessionHistory[]>(
    queryKey('chat:sessions', orgId, agentId),
    async () => {
      const sessions = await chatApi.listSessions(orgId, agentId)
      // Filter out orchestration sessions - they should only appear in the orchestration chat page
      return sessions.filter(session => session.agent_ids && session.agent_ids.length > 0)
    },
  )

  const sessions = useMemo(() => data ?? EMPTY, [data])

  // Local-only update — used to reflect the backend's auto-generated title,
  // which the server already persists on its own.
  const updateSessionName = useCallback(
    (threadId: string, name: string) => {
      mutate(prev => prev?.map(s => (s.thread_id === threadId ? { ...s, name } : s)))
    },
    [mutate],
  )

  // Manual rename — optimistically updates, persists to the backend, and rolls
  // back if the request fails.
  const renameSession = useCallback(
    async (threadId: string, name: string) => {
      const trimmed = name.trim()
      if (!trimmed) return
      let snapshot: ChatSessionHistory[] | undefined
      mutate(prev => {
        snapshot = prev
        return prev?.map(s => (s.thread_id === threadId ? { ...s, name: trimmed } : s))
      })
      try {
        await chatApi.renameSession(threadId, trimmed)
      } catch (e) {
        mutate(() => snapshot)
        throw e
      }
    },
    [mutate],
  )

  // Delete a session — calls the backend, then removes from local state.
  const removeSession = useCallback(
    async (threadId: string) => {
      let snapshot: ChatSessionHistory[] | undefined
      mutate(prev => {
        snapshot = prev
        return prev?.filter(s => s.thread_id !== threadId)
      })
      try {
        await chatApi.deleteSession(threadId)
      } catch {
        mutate(() => snapshot)
      }
    },
    [mutate],
  )

  return {
    data: sessions,
    loading,
    error,
    refetch,
    updateSessionName,
    renameSession,
    removeSession,
  }
}
