'use client'

import { useState, useEffect, useCallback } from 'react'
import { connectorsApi } from '@/lib/api'
import type { ConnectorStatusState } from '@/types/connectors'

/**
 * Single shared owner of "what does connector status mean," including the
 * failure case. `connectorsApi.getStatus` already retries transient errors
 * (429/5xx/network) — if it still fails after retrying, that connector's
 * entry is marked `checkFailed: true` rather than being treated as
 * `connected: false`, so callers can render "couldn't verify" distinctly
 * from a real "not connected" answer.
 */
export function useConnectorStatuses(connectorIds: string[]) {
  const [statuses, setStatuses] = useState<Record<string, ConnectorStatusState>>({})
  const [loading, setLoading] = useState(false)

  const fetchIds = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return
    setLoading(true)
    const results = await Promise.allSettled(
      ids.map(id => connectorsApi.getStatus(id).then(s => ({ id, status: s })))
    )
    setStatuses(prev => {
      const next = { ...prev }
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          next[r.value.id] = r.value.status
        } else {
          next[ids[i]] = { connected: false, checkFailed: true }
        }
      })
      return next
    })
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchIds(connectorIds)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectorIds.join(',')])

  const setStatus = useCallback((id: string, status: ConnectorStatusState) => {
    setStatuses(prev => ({ ...prev, [id]: status }))
  }, [])

  const refetch = useCallback(() => fetchIds(connectorIds), [fetchIds, connectorIds])

  const retryOne = useCallback((id: string) => fetchIds([id]), [fetchIds])

  return { statuses, loading, setStatus, refetch, retryOne }
}
