'use client'

import { useState, useEffect, useCallback } from 'react'
import { agentsApi } from '@/lib/api'
import type { ConnectorPermissions } from '@/types'

export function useAgentPermissions(agentId?: string) {
  const [permissions, setPermissions] = useState<Record<string, boolean>>({}) // tools permissions
  const [connectorsPermissions, setConnectorsPermissions] = useState<Record<string, ConnectorPermissions>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    if (!agentId) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await agentsApi.getPermissions(agentId)
      setPermissions(res.permissions?.tools ?? {})
      setConnectorsPermissions(res.permissions?.connectors ?? {})
    } catch (e: unknown) {
      // 404 is expected if no permissions doc exists yet
      setPermissions({})
      setConnectorsPermissions({})
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => {
    fetch()
  }, [fetch])

  const updatePermissions = useCallback(async (tools?: Record<string, boolean>, connectors?: Record<string, ConnectorPermissions>) => {
    if (!agentId) return
    setError(null)
    try {
      const res = await agentsApi.patchPermissions(agentId, { ...(tools ? { tools } : {}), connectors })
      setPermissions(res.permissions?.tools ?? {})
      setConnectorsPermissions(res.permissions?.connectors ?? {})
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update agent permissions')
      throw e
    }
  }, [agentId])

  return { permissions, setPermissions, connectorsPermissions, setConnectorsPermissions, loading, error, refetch: fetch, updatePermissions }
}
