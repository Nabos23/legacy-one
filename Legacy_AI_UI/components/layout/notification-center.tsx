'use client'

import { useState } from 'react'
import { Bot, Wrench, AlertTriangle, CheckCircle2, Settings, Bell, X, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import type { NotificationPublic } from '@/types'

/** Compact relative-time label, e.g. "2m ago", "3h ago", "Yesterday". */
function timeAgo(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = Date.now() - then
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'Just now'
  if (min < 60) return `${min}m ago`
  const hrs = Math.floor(min / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

const iconMap = {
  agent:   { Icon: Bot,           bg: 'bg-violet-100 dark:bg-violet-900/30', color: 'text-violet-600 dark:text-violet-400' },
  tool:    { Icon: Wrench,        bg: 'bg-cyan-100 dark:bg-cyan-900/30',     color: 'text-cyan-600 dark:text-cyan-400' },
  alert:   { Icon: AlertTriangle, bg: 'bg-amber-100 dark:bg-amber-900/30',   color: 'text-amber-600 dark:text-amber-400' },
  success: { Icon: CheckCircle2,  bg: 'bg-green-100 dark:bg-green-900/30',   color: 'text-green-600 dark:text-green-400' },
  system:  { Icon: Settings,      bg: 'bg-[var(--surface-2)]',               color: 'text-[var(--text-3)]' },
}

interface NotificationCenterProps {
  open: boolean
  onClose: () => void
  notifications: NotificationPublic[]
  loading: boolean
  error: string | null
  onMarkAllRead: () => void
  onDismiss: (id: string) => void
}

export function NotificationCenter({
  open,
  onClose,
  notifications,
  loading,
  error,
  onMarkAllRead,
  onDismiss,
}: NotificationCenterProps) {
  const [tab, setTab] = useState<'all' | 'unread'>('all')

  const unreadCount = notifications.filter(n => !n.read).length
  const markAllRead = onMarkAllRead
  const dismiss = onDismiss
  const visible = tab === 'unread' ? notifications.filter(n => !n.read) : notifications

  if (!open) return null

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />

      <div className="fixed right-0 top-[56px] h-[calc(100vh-56px)] w-[min(380px,100vw)] z-50
        flex flex-col animate-slideInRight
        bg-white/92 dark:bg-[#0e0e20]/96
        backdrop-blur-2xl
        border-l border-black/[0.08] dark:border-white/[0.08]
        shadow-[-8px_0_40px_rgba(0,0,0,0.08)] dark:shadow-[-8px_0_40px_rgba(0,0,0,0.5)]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4
          border-b border-black/[0.06] dark:border-white/[0.06]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-violet-100 dark:bg-violet-900/30
              flex items-center justify-center">
              <Bell className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400" />
            </div>
            <span className="text-[15px] font-bold text-[var(--text-1)]">Notifications</span>
            {unreadCount > 0 && (
              <span className="w-5 h-5 rounded-full bg-violet-600 text-white text-[10px]
                font-bold flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {unreadCount > 0 && (
              <Button variant="ghost" size="xs" onClick={markAllRead}
                className="text-[11px] text-violet-600 dark:text-violet-400 hover:text-violet-700">
                Mark all read
              </Button>
            )}
            <Button variant="ghost" size="icon-xs" onClick={onClose}
              className="text-[var(--text-3)] hover:text-[var(--text-1)]">
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="px-4 pt-3 pb-2">
          <Tabs
            value={tab}
            onChange={v => setTab(v as typeof tab)}
            tabs={[
              { value: 'all', label: 'All' },
              {
                value: 'unread',
                label: (
                  <span className="flex items-center gap-1.5">
                    Unread
                    {unreadCount > 0 && (
                      <span className="w-4 h-4 rounded-full bg-violet-500 text-white text-[9px] font-bold flex items-center justify-center">
                        {unreadCount}
                      </span>
                    )}
                  </span>
                ),
              },
            ]}
          />
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-3 space-y-2">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="flex items-start gap-3 px-3 py-3 animate-pulse">
                  <div className="w-8 h-8 rounded-xl bg-black/[0.06] dark:bg-white/[0.08] shrink-0" />
                  <div className="flex-1 space-y-2 pt-1">
                    <div className="h-3 rounded bg-black/[0.06] dark:bg-white/[0.08] w-2/3" />
                    <div className="h-2.5 rounded bg-black/[0.04] dark:bg-white/[0.05] w-full" />
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--text-3)] px-6 text-center">
              <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-red-500 dark:text-red-400 opacity-70" />
              </div>
              <p className="text-[14px] font-semibold text-[var(--text-2)]">Couldn&apos;t load notifications</p>
              <p className="text-[12px]">{error}</p>
            </div>
          ) : visible.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--text-3)] px-6">
              <div className="w-14 h-14 rounded-2xl bg-[var(--surface-2)] border border-[var(--border)]
                flex items-center justify-center">
                <Sparkles className="w-6 h-6 opacity-40" />
              </div>
              <p className="text-[14px] font-semibold text-[var(--text-2)]">All caught up!</p>
              <p className="text-[12px] text-center">No {tab === 'unread' ? 'unread ' : ''}notifications right now.</p>
            </div>
          ) : (
            <div className="px-3 py-1">
              {visible.map((n, i) => {
                const { Icon, bg, color } = iconMap[n.type]
                return (
                  <div
                    key={n.id}
                    className={cn(
                      'group flex items-start gap-3 px-3 py-3 rounded-xl mb-0.5',
                      'hover:bg-black/[0.03] dark:hover:bg-white/[0.04]',
                      'transition-colors duration-150',
                      !n.read && 'bg-violet-50/50 dark:bg-violet-950/20'
                    )}
                  >
                    {/* Unread dot */}
                    <div className="flex flex-col items-center gap-1.5 mt-1">
                      {!n.read ? (
                        <span className="w-2 h-2 rounded-full bg-violet-500 shrink-0
                          shadow-[0_0_6px_rgba(124,58,237,0.6)]" />
                      ) : (
                        <span className="w-2 h-2 shrink-0" />
                      )}
                    </div>

                    {/* Icon */}
                    <div className={cn('w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5', bg)}>
                      <Icon className={cn('w-4 h-4', color)} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        'text-[13px] leading-snug',
                        !n.read ? 'font-semibold text-[var(--text-1)]' : 'font-medium text-[var(--text-2)]'
                      )}>
                        {n.title}
                      </p>
                      <p className="text-[12px] text-[var(--text-3)] mt-0.5 leading-snug">{n.message}</p>
                      <p className="text-[11px] text-[var(--text-3)] mt-1 opacity-70">{timeAgo(n.created_at)}</p>
                    </div>

                    {/* Dismiss */}
                    <button
                      type="button"
                      onClick={() => dismiss(n.id)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity
                        text-[var(--text-3)] hover:text-[var(--text-1)] mt-1 shrink-0"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-black/[0.06] dark:border-white/[0.06]">
          <button type="button"
            className="w-full text-center text-[13px] font-medium text-violet-600 dark:text-violet-400
              hover:text-violet-700 dark:hover:text-violet-300 transition-colors py-1">
            View all activity →
          </button>
        </div>
      </div>
    </>
  )
}
