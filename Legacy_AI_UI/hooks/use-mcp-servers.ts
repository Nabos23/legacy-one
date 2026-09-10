'use client'

import { useState, useEffect, useCallback } from 'react'
import { mcpApi } from '@/lib/api'
import type { McpServerPublic, McpToolSpec, McpAgentToolPublic, Page } from '@/types'

export interface UseMcpServersFilters {
  search?: string
  status?: string
  agentId?: string
}

export function useMcpServers(page = 1, pageSize = 20, filters: UseMcpServersFilters = {}) {
  const [data, setData] = useState<Page<McpServerPublic> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { search, status, agentId } = filters

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await mcpApi.list(page, pageSize, search, status, agentId))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load MCP servers')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, search, status, agentId])

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function useMcpServersByAgent(agentId: string | null) {
  const [data, setData] = useState<McpServerPublic[]>([])
  const [loading, setLoading] = useState(false)

  const fetch = useCallback(async () => {
    if (!agentId) { setData([]); return }
    setLoading(true)
    try {
      const res = await mcpApi.listByAgent(agentId)
      setData(res.items)
    } catch {
      setData([])
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, refetch: fetch }
}

/** A single connected server's discovered tools (for a per-tool picker). */
export function useMcpServerTools(serverId: string | null) {
  const [data, setData] = useState<McpToolSpec[]>([])
  const [loading, setLoading] = useState(false)

  const fetch = useCallback(async () => {
    if (!serverId) { setData([]); return }
    setLoading(true)
    try {
      setData(await mcpApi.serverTools(serverId))
    } catch {
      setData([])
    } finally {
      setLoading(false)
    }
  }, [serverId])

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, refetch: fetch }
}

/** The individual MCP tools attached to one agent (across any number of servers).
 * Fetches every page — this feeds a checkbox picker that needs the complete
 * attached set, not a paginated view, so a fixed page-1-only call would
 * silently under-report once an agent has more attached tools than one page. */
export function useAgentMcpTools(agentId: string | null) {
  const [data, setData] = useState<McpAgentToolPublic[]>([])
  const [loading, setLoading] = useState(false)

  const fetch = useCallback(async () => {
    if (!agentId) { setData([]); return }
    setLoading(true)
    try {
      const pageSize = 100
      let page = 1
      let all: McpAgentToolPublic[] = []
      while (true) {
        const res = await mcpApi.agentTools(agentId, page, pageSize)
        all = all.concat(res.items)
        if (all.length >= res.total || res.items.length === 0) break
        page += 1
      }
      setData(all)
    } catch {
      setData([])
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, refetch: fetch }
}
