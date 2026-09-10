'use client'

import { useCallback, useMemo } from 'react'
import { notificationsApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useApiQuery, queryKey } from '@/hooks/use-api-query'
import type { NotificationPublic, Page } from '@/types'

const EMPTY: NotificationPublic[] = []

/**
 * Loads the current user's notifications from the backend and exposes
 * optimistic mark-all-read / dismiss actions. Only fetches once authenticated.
 */
export function useNotifications() {
  const { isAuthenticated, user } = useAuth()

  const { data, loading, error, refetch, mutate } = useApiQuery<Page<NotificationPublic>>(
    queryKey('notifications', user?.id),
    () => notificationsApi.list(1, 50),
    { enabled: isAuthenticated },
  )

  const items = useMemo(() => data?.items ?? EMPTY, [data])

  const markAllRead = useCallback(async () => {
    mutate(prev => (prev ? { ...prev, items: prev.items.map(n => ({ ...n, read: true })) } : prev))
    try {
      await notificationsApi.markAllRead()
    } catch {
      refetch()
    }
  }, [mutate, refetch])

  const dismiss = useCallback(
    async (id: string) => {
      let snapshot: Page<NotificationPublic> | undefined
      mutate(prev => {
        snapshot = prev
        return prev ? { ...prev, items: prev.items.filter(n => n.id !== id) } : prev
      })
      try {
        await notificationsApi.dismiss(id)
      } catch {
        mutate(() => snapshot)
      }
    },
    [mutate],
  )

  const unreadCount = useMemo(() => items.filter(n => !n.read).length, [items])

  return {
    items,
    loading: isAuthenticated ? loading : false,
    error,
    unreadCount,
    refetch,
    markAllRead,
    dismiss,
  }
}
