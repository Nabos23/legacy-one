import { api } from './client'
import type { NotificationPublic, Page } from '@/types'

export const notificationsApi = {
  /** List the caller's notifications (own + org-wide), newest first. */
  list: (page = 1, page_size = 50) =>
    api.get<Page<NotificationPublic>>(
      `/notifications?page=${page}&page_size=${page_size}`
    ),

  /** Number of unread notifications for the caller. */
  unreadCount: () => api.get<{ unread: number }>('/notifications/unread-count'),

  /** Mark a single notification as read. */
  markRead: (id: string) =>
    api.patch<NotificationPublic>(`/notifications/${id}/read`, {}),

  /** Mark every visible notification as read. */
  markAllRead: () => api.post<void>('/notifications/read-all', {}),

  /** Dismiss (soft-delete) a notification. */
  dismiss: (id: string) => api.delete<void>(`/notifications/${id}`),
}
