'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, Unplug } from 'lucide-react'
import { connectorsApi } from '@/lib/api/connectors'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'

export interface ConnectorAuthErrorInfo {
  connector_id?: string | null
  provider_id?: string | null
  display_name?: string | null
}

export function ReconnectButton({
  connectorId,
  displayName,
  onReconnected,
  hasEverConnected,
}: {
  connectorId: string
  displayName?: string | null
  onReconnected?: () => void
  hasEverConnected?: boolean | null
}) {
  const { toast } = useToast()
  const [connecting, setConnecting] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const actionWord = hasEverConnected === false ? 'Connect' : 'Reconnect'

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => stopPolling, [stopPolling])

  const handleReconnect = useCallback(async () => {
    setConnecting(true)
    try {
      await connectorsApi.getStatus(connectorId).catch(() => null)
      const { url } = await connectorsApi.getAuthUrl(connectorId)
      if (!url) {
        toast.info(`${displayName || 'This connector'} already looks connected — try your message again.`)
        setConnecting(false)
        onReconnected?.()
        return
      }

      const popup = window.open(url, 'connector-reconnect', 'width=560,height=720')
      if (!popup) {
        toast.error('Please allow popups for this site to reconnect the connector.')
        setConnecting(false)
        return
      }

      pollRef.current = setInterval(async () => {
        if (popup.closed) {
          stopPolling()
          setConnecting(false)
          return
        }
        try {
          const s = await connectorsApi.getStatus(connectorId)
          if (s.connected) {
            stopPolling()
            popup.close()
            setConnecting(false)
            toast.success(`${displayName || 'Connector'} reconnected.`)
            onReconnected?.()
          }
        } catch {
          // A transient status-check failure shouldn't abort the flow — keep polling.
        }
      }, 2000)
    } catch (err: any) {
      toast.error(err?.message || 'Failed to start the reconnect flow')
      setConnecting(false)
    }
  }, [connectorId, displayName, onReconnected, stopPolling, toast])

  return (
    <button
      onClick={handleReconnect}
      disabled={connecting}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium bg-amber-500 hover:bg-amber-600 disabled:opacity-60 disabled:cursor-not-allowed text-white transition-colors shrink-0"
    >
      {connecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Unplug className="w-3.5 h-3.5" />}
      {connecting ? 'Waiting…' : `${actionWord}${displayName ? ` ${displayName}` : ''}`}
    </button>
  )
}

function ConnectorAuthErrorRow({
  error,
  onReconnected,
}: {
  error: ConnectorAuthErrorInfo & { connector_id: string }
  onReconnected?: (connectorId: string) => void
}) {
  const [hasEverConnected, setHasEverConnected] = useState<boolean | null>(null)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    let cancelled = false
    connectorsApi
      .getStatus(error.connector_id)
      .then(s => {
        if (!cancelled) setHasEverConnected(!!s.connected_at)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [error.connector_id])

  const actionWord = hasEverConnected === false ? 'connected' : 'reconnected'

  const handleReconnected = useCallback(() => {

    setExiting(true)
    setTimeout(() => onReconnected?.(error.connector_id), 200)
  }, [error.connector_id, onReconnected])

  return (
    <div
      className={cn(
        'flex items-center gap-2 flex-wrap px-3 py-2 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 text-[12px] text-amber-700 dark:text-amber-400',
        'transition-[opacity,transform] duration-200 ease-out',
        exiting ? 'opacity-0 -translate-y-1' : 'animate-fadeIn opacity-100',
      )}
    >
      <span>
        {error.display_name || 'A connector'} needs to be {actionWord} to continue.
      </span>
      <ReconnectButton
        connectorId={error.connector_id}
        displayName={error.display_name}
        onReconnected={handleReconnected}
        hasEverConnected={hasEverConnected}
      />
    </div>
  )
}

export function ConnectorAuthErrorBanner({
  errors,
  onReconnected,
}: {
  errors: ConnectorAuthErrorInfo[]
  onReconnected?: (connectorId: string) => void
}) {
  const withId = errors.filter((e): e is ConnectorAuthErrorInfo & { connector_id: string } => !!e.connector_id)
  if (!withId.length) return null

  // De-dupe by connector_id in case the same connector failed on more than one tool call.
  const seen = new Set<string>()
  const unique = withId.filter(e => (seen.has(e.connector_id) ? false : (seen.add(e.connector_id), true)))

  return (
    <div className="mt-2 flex flex-col gap-2">
      {unique.map(e => (
        <ConnectorAuthErrorRow key={e.connector_id} error={e} onReconnected={onReconnected} />
      ))}
    </div>
  )
}
