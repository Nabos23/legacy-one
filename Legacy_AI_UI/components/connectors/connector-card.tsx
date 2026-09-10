'use client'

import { useState } from 'react'
import { Loader2, Unplug, Settings, Zap, AlertTriangle, RefreshCw, Info, ListChecks } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { connectorsApi } from '@/lib/api/connectors'
import { useToast } from '@/hooks/use-toast'
import { ConnectorLogo } from './connector-logo'
import { ConnectorSetupDialog } from './connector-setup-dialog'
import type { ConnectorStatusState, ConnectorWithStatus } from '@/types/connectors'
import { cn, formatDate } from '@/lib/utils'

interface ConnectorCardProps {
  connector: ConnectorWithStatus
  onStatusChange: () => void | Promise<void>
  /** Patch this connector's status in the shared cache without waiting on a
   * round-trip — used to make disconnect feel instant, with `onStatusChange`
   * (a real refetch) as the rollback path if the request fails. */
  onOptimisticStatus?: (status: ConnectorStatusState) => void
}

/** Human-readable labels for the `last_error` codes the backend can report
 * (see backend/connectors/services.py's RefreshFailure enum + disconnect reasons). */
export const CONNECTOR_ERROR_LABELS: Record<string, string> = {
  permanent: 'Reauthorization required',
  transient: 'Temporary connection issue',
  user_disconnected: 'Disconnected',
  slack_revoked: 'Access revoked by Slack',
  not_connected: 'Not connected',
}

export const humanizeConnectorError = (code: string) => CONNECTOR_ERROR_LABELS[code] ?? code

/** "create_issue" -> "Create issue" */
export const humanizeAction = (action: string) => {
  const spaced = action.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

const CATEGORY_CONFIG: Record<string, { badge: string; glow: string; accent: string }> = {
  Storage:      { badge: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',     glow: 'hover:shadow-blue-500/10',    accent: 'from-blue-500/5'    },
  Email:        { badge: 'bg-red-500/10 text-red-600 dark:text-red-400',        glow: 'hover:shadow-red-500/10',     accent: 'from-red-500/5'     },
  Messaging:    { badge: 'bg-violet-500/10 text-violet-600 dark:text-violet-400', glow: 'hover:shadow-violet-500/10', accent: 'from-violet-500/5'  },
  Productivity: { badge: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400', glow: 'hover:shadow-emerald-500/10', accent: 'from-emerald-500/5' },
  CRM:          { badge: 'bg-orange-500/10 text-orange-600 dark:text-orange-400', glow: 'hover:shadow-orange-500/10', accent: 'from-orange-500/5'  },
  Support:          { badge: 'bg-teal-500/10 text-teal-600 dark:text-teal-400',       glow: 'hover:shadow-teal-500/10',      accent: 'from-teal-500/5'      },
  ITSM:             { badge: 'bg-green-500/10 text-green-600 dark:text-green-400',     glow: 'hover:shadow-green-500/10',     accent: 'from-green-500/5'     },
  Analytics:        { badge: 'bg-orange-500/10 text-orange-600 dark:text-orange-400',  glow: 'hover:shadow-orange-500/10',    accent: 'from-orange-500/5'    },
  Design:           { badge: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',  glow: 'hover:shadow-purple-500/10',    accent: 'from-purple-500/5'    },
  'E-Commerce':     { badge: 'bg-lime-500/10 text-lime-600 dark:text-lime-400',        glow: 'hover:shadow-lime-500/10',      accent: 'from-lime-500/5'      },
  'Knowledge Base': { badge: 'bg-sky-500/10 text-sky-600 dark:text-sky-400',           glow: 'hover:shadow-sky-500/10',       accent: 'from-sky-500/5'       },
  Freelance:        { badge: 'bg-green-500/10 text-green-600 dark:text-green-400',     glow: 'hover:shadow-green-500/10',     accent: 'from-green-500/5'     },
  Health:           { badge: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',        glow: 'hover:shadow-rose-500/10',      accent: 'from-rose-500/5'      },
  Video:            { badge: 'bg-sky-500/10 text-sky-600 dark:text-sky-400',            glow: 'hover:shadow-sky-500/10',       accent: 'from-sky-500/5'       },
  Marketing:        { badge: 'bg-pink-500/10 text-pink-600 dark:text-pink-400',         glow: 'hover:shadow-pink-500/10',      accent: 'from-pink-500/5'      },
  'Social Media':   { badge: 'bg-violet-500/10 text-violet-600 dark:text-violet-400',   glow: 'hover:shadow-violet-500/10',    accent: 'from-violet-500/5'    },
  HR:               { badge: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',      glow: 'hover:shadow-amber-500/10',     accent: 'from-amber-500/5'     },
  Monitoring:       { badge: 'bg-red-500/10 text-red-600 dark:text-red-400',            glow: 'hover:shadow-red-500/10',       accent: 'from-red-500/5'       },
  'Developer Tools':{ badge: 'bg-slate-500/10 text-slate-600 dark:text-slate-400',      glow: 'hover:shadow-slate-500/10',     accent: 'from-slate-500/5'     },
  'Project Management':{ badge: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400',glow: 'hover:shadow-indigo-500/10',    accent: 'from-indigo-500/5'    },
  Finance:          { badge: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',glow: 'hover:shadow-emerald-500/10',   accent: 'from-emerald-500/5'   },
  Payments:         { badge: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400',   glow: 'hover:shadow-indigo-500/10',    accent: 'from-indigo-500/5'    },
  Communication:    { badge: 'bg-red-500/10 text-red-600 dark:text-red-400',            glow: 'hover:shadow-red-500/10',       accent: 'from-red-500/5'       },
  Documents:        { badge: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',   glow: 'hover:shadow-yellow-500/10',    accent: 'from-yellow-500/5'    },
}

const FALLBACK_CONFIG = { badge: 'bg-gray-500/10 text-gray-500', glow: 'hover:shadow-gray-500/10', accent: 'from-gray-500/5' }

export function ConnectorCard({ connector, onStatusChange, onOptimisticStatus }: ConnectorCardProps) {
  const [setupOpen, setSetupOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [actionsOpen, setActionsOpen] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const { toast } = useToast()

  const isConnected = connector.status?.connected ?? false
  const checkFailed = connector.status?.checkFailed ?? false
  const cfg = CATEGORY_CONFIG[connector.category] ?? FALLBACK_CONFIG

  const handleDisconnect = async () => {
    setConfirmOpen(false)
    const previousStatus = connector.status
    // Optimistic: the card flips to "Not connected" immediately; only pay for
    // a real refetch afterwards to reconcile fields we didn't set locally
    // (e.g. `last_error`). Roll back if the request actually fails.
    onOptimisticStatus?.({ connected: false })
    setDisconnecting(true)
    try {
      await connectorsApi.disconnect(connector.id)
      onStatusChange()
    } catch (e) {
      if (previousStatus) onOptimisticStatus?.(previousStatus)
      toast.error(e instanceof Error ? e.message : 'Failed to disconnect')
    } finally {
      setDisconnecting(false)
    }
  }

  const handleRetryStatus = async () => {
    setRetrying(true)
    try {
      await onStatusChange()
    } finally {
      setRetrying(false)
    }
  }

  return (
    <>
      <div
        className={cn(
          'group relative flex flex-col rounded-2xl overflow-hidden',
          'transition-[border-color,box-shadow,transform] duration-300 ease-out',
          // Glassmorphism base
          'bg-white/80 dark:bg-white/[0.035]',
          'backdrop-blur-sm',
          'border border-black/[0.06] dark:border-white/[0.08]',
          'shadow-sm',
            // Hover lift + category glow
          'hover:-translate-y-0.5 hover:shadow-lg',
          cfg.glow,
          // Connected: subtle green shimmer on border
          isConnected && 'border-green-400/25 dark:border-green-500/20 shadow-green-500/5',
        )}
      >
        {/* Category color wash — very subtle gradient at top */}
        <div className={cn('absolute inset-x-0 top-0 h-24 bg-gradient-to-b opacity-60 dark:opacity-40 pointer-events-none', cfg.accent, 'to-transparent')} />

        {/* Connected shimmer strip at top edge */}
        {isConnected && (
          <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-green-400/60 to-transparent" />
        )}

        <div className="relative p-5 flex flex-col gap-4 h-full">
          {/* Top row: logo + status */}
          <div className="flex items-start justify-between gap-3">
            <ConnectorLogo providerId={connector.provider_id} size="md" />

            <div className="flex items-center shrink-0">
              {connector.statusLoading ? (
                <span className="flex items-center gap-1.5 text-[11px] text-[var(--text-3)] bg-black/[0.04] dark:bg-white/[0.05] px-2.5 py-1 rounded-full">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Checking
                </span>
              ) : checkFailed ? (
                <button
                  type="button"
                  onClick={handleRetryStatus}
                  disabled={retrying}
                  className="flex items-center gap-1.5 text-[11px] font-medium text-amber-700 dark:text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full hover:bg-amber-500/15 transition-colors disabled:opacity-60"
                  title="Couldn't verify connection status — click to retry"
                >
                  <RefreshCw className={cn('w-3 h-3', retrying && 'animate-spin')} />
                  Couldn't verify
                </button>
              ) : isConnected ? (
                <span className="flex items-center gap-1.5 text-[11px] font-medium text-green-700 dark:text-green-400 bg-green-500/10 dark:bg-green-500/10 px-2.5 py-1 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.7)]" />
                  Connected
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-[11px] text-[var(--text-3)] bg-black/[0.04] dark:bg-white/[0.05] px-2.5 py-1 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-3)]/50" />
                  Not connected
                </span>
              )}
            </div>
          </div>

          {/* Connection health — relative "connected since" or the last error */}
          {!connector.statusLoading && !checkFailed && (
            isConnected && connector.status?.connected_at ? (
              <p className="text-[10.5px] text-[var(--text-3)] -mt-2 text-right">
                Connected {formatDate(connector.status.connected_at)}
              </p>
            ) : !isConnected && connector.status?.last_error ? (
              <p className="text-[10.5px] text-red-500 dark:text-red-400 -mt-2 text-right">
                {humanizeConnectorError(connector.status.last_error)}
              </p>
            ) : null
          )}

          {/* Name + category chip + description */}
          <div className="space-y-2 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-[13.5px] font-semibold text-[var(--text-1)] leading-snug">
                {connector.name}
              </h3>
              <span className={cn('text-[9.5px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full', cfg.badge)}>
                {connector.category}
              </span>
              {connector.available_actions.length > 0 && (
                <button
                  type="button"
                  onClick={() => setActionsOpen(true)}
                  aria-label={`View ${connector.available_actions.length} available actions`}
                  title={`${connector.available_actions.length} available action${connector.available_actions.length === 1 ? '' : 's'}`}
                  className="flex items-center gap-1 h-4 px-1.5 rounded-full text-[9.5px] font-medium text-[var(--text-3)] hover:text-[var(--text-1)] bg-black/[0.03] dark:bg-white/[0.04] hover:bg-black/[0.05] dark:hover:bg-white/[0.08] transition-colors"
                >
                  <Info className="w-3 h-3 shrink-0" />
                  {connector.available_actions.length}
                </button>
              )}
            </div>
            <p className="text-[12px] text-[var(--text-3)] leading-relaxed line-clamp-2">
              {connector.description}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 pt-1">
            {isConnected ? (
              <>
                <Button
                  variant="outline"
                  size="xs"
                  className="flex-1 text-[12px] h-8 border-black/10 dark:border-white/10 hover:bg-black/[0.03] dark:hover:bg-white/[0.05]"
                  onClick={() => setSetupOpen(true)}
                >
                  <Settings className="w-3.5 h-3.5 mr-1.5 opacity-70" />
                  Manage
                </Button>
                <Button
                  variant="outline"
                  size="xs"
                  className="text-[12px] h-8 border-red-200/60 dark:border-red-900/40 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10"
                  onClick={() => setConfirmOpen(true)}
                  disabled={disconnecting}
                >
                  {disconnecting
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <Unplug className="w-3.5 h-3.5" />
                  }
                </Button>
              </>
            ) : (
              <Button
                size="xs"
                className="flex-1 text-[12px] h-8 bg-[var(--text-1)] hover:bg-[var(--text-1)]/90 dark:bg-white dark:text-black dark:hover:bg-white/90 text-white font-medium"
                onClick={() => setSetupOpen(true)}
              >
                <Zap className="w-3.5 h-3.5 mr-1.5 opacity-80" />
                Connect
              </Button>
            )}
          </div>
        </div>
      </div>

      <Dialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Disconnect"
        size="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="bg-red-600 hover:bg-red-700 text-white"
              onClick={handleDisconnect}
            >
              Disconnect
            </Button>
          </div>
        }
      >
        <div className="flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
            <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <p className="text-[14px] font-medium text-[var(--text-1)]">
              Are you sure you want to disconnect?
            </p>
            <p className="mt-1 text-[13px] text-[var(--text-3)]">
              This will disconnect <strong>{connector.name}</strong>. You can reconnect anytime.
            </p>
          </div>
        </div>
      </Dialog>

      <ConnectorSetupDialog
        connector={connector}
        status={connector.status}
        open={setupOpen}
        onOpenChange={setSetupOpen}
        onConnected={onStatusChange}
      />

      <Dialog
        open={actionsOpen}
        onOpenChange={setActionsOpen}
        title={`${connector.name} — Available actions`}
        size="sm"
      >
        <div className="space-y-1">
          <p className="text-[12.5px] text-[var(--text-3)] mb-3">
            Actions an agent can perform through this connector once it's connected.
          </p>
          <ul className="space-y-1.5">
            {connector.available_actions.map((action) => (
              <li
                key={action}
                className="flex items-center gap-2 text-[13px] text-[var(--text-1)] bg-black/[0.03] dark:bg-white/[0.04] px-3 py-2 rounded-lg"
              >
                <ListChecks className="w-3.5 h-3.5 shrink-0 text-[var(--text-3)]" />
                {humanizeAction(action)}
              </li>
            ))}
          </ul>
        </div>
      </Dialog>
    </>
  )
}
