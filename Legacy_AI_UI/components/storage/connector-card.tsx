'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Loader2,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { driveApi } from '@/lib/api/drive'
import { oneDriveApi } from '@/lib/api/onedrive'

export interface ConnectorCardProvider {
  id: 'google-drive' | 'onedrive'
  name: string
  icon: LucideIcon
  filesHref: string
  color: string
}

interface ConnectorCardProps {
  provider: ConnectorCardProvider
}

export function ConnectorCard({ provider }: ConnectorCardProps) {
  const pathname = usePathname()
  const [connected, setConnected] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)

  const api = provider.id === 'google-drive' ? driveApi : oneDriveApi
  const Icon = provider.icon
  const isActive = pathname?.startsWith(provider.filesHref) ?? false

  const checkStatus = useCallback(async () => {
    setLoading(true)
    try {
      const { connected: isConnected } = await api.getStatus()
      setConnected(isConnected)
    } catch {
      setConnected(false)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    checkStatus()
  }, [checkStatus])

  useEffect(() => {
    const onDisconnected = (e: CustomEvent<{ providerId: string }>) => {
      if (e.detail.providerId === provider.id) {
        checkStatus()
      }
    }
    window.addEventListener('storage:disconnected', onDisconnected as EventListener)
    return () => window.removeEventListener('storage:disconnected', onDisconnected as EventListener)
  }, [provider.id, checkStatus])

  return (
    <Link
      href={provider.filesHref}
      className={cn(
        'group relative flex items-center gap-3 mx-2 px-3 py-2.5 rounded-xl',
        'transition-[background-color] duration-200',
        isActive
          ? 'bg-gradient-to-r from-violet-500/15 to-violet-500/5 dark:from-violet-500/20 dark:to-violet-500/5'
          : 'hover:bg-black/[0.045] dark:hover:bg-white/[0.05]',
      )}
    >
      {/* Active indicator */}
      {isActive && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-violet-500 dark:bg-violet-400" />
      )}

      {/* Icon */}
      <span
        className={cn(
          'flex size-8 items-center justify-center rounded-lg shrink-0',
          'transition-colors duration-200',
          provider.color,
          isActive ? 'shadow-sm' : '',
        )}
      >
        <Icon className="w-4 h-4 text-white" />
      </span>

      {/* Label + status */}
      <div className="flex-1 min-w-0">
        <p
          className={cn(
            'text-[13px] font-medium truncate transition-colors',
            isActive
              ? 'text-violet-700 dark:text-violet-300'
              : 'text-[var(--text-2)] group-hover:text-[var(--text-1)]',
          )}
        >
          {provider.name}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          {loading ? (
            <span className="flex items-center gap-1 text-[11px] text-[var(--text-3)]">
              <Loader2 className="w-2.5 h-2.5 animate-spin" />
              Checking...
            </span>
          ) : connected ? (
            <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
              <span className="relative flex size-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 dark:bg-emerald-400 opacity-75" />
                <span className="relative inline-flex size-1.5 rounded-full bg-emerald-500" />
              </span>
              Connected
            </span>
          ) : (
            <span className="text-[11px] text-[var(--text-3)]">Not connected</span>
          )}
        </div>
      </div>

      {/* Active glow dot */}
      {isActive && (
        <span
          className="ml-auto w-[6px] h-[6px] rounded-full bg-violet-500 dark:bg-violet-400 shrink-0
            shadow-[0_0_6px_2px_rgba(124,58,237,0.5)] dark:shadow-[0_0_6px_2px_rgba(167,139,250,0.5)]"
        />
      )}
    </Link>
  )
}
