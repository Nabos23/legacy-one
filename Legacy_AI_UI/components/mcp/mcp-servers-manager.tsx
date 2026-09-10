'use client'

import { useState } from 'react'
import { Plug, RefreshCw, Trash2, ToggleLeft, ToggleRight, Wrench, AlertCircle, Bot } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/search-input'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { DataTable } from '@/components/ui/data-table'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { McpStatusBadge, McpTransportBadge } from '@/components/mcp/mcp-status-badge'
import { ConnectMcpSheet } from '@/components/mcp/connect-mcp-sheet'
import { McpInfoCard } from '@/components/mcp/mcp-info-card'
import { useMcpServers } from '@/hooks/use-mcp-servers'
import { useAgents } from '@/hooks/use-agents'
import { mcpApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import type { McpServerPublic } from '@/types'
import { formatDate } from '@/lib/utils'

type StatusFilter = 'all' | 'connected' | 'error' | 'pending'

interface Props {
  title?: string
  description?: string
}

/**
 * Standalone MCP server management — connect a server independent of any
 * agent, browse every server connected in the org, and manage it (refresh,
 * enable/disable, delete). Shared between /admin/mcp-servers and
 * /client/mcp-servers so both surfaces stay identical instead of drifting
 * apart as two copies. Per-tool attachment to a specific agent happens on the
 * agent's own "MCP Servers" step (components/mcp/agent-mcp-step.tsx), which
 * reads/writes the same backend data this page shows.
 */
export function McpServersManager({
  title = 'MCP Servers',
  description = 'Connect external MCP servers — stdio, HTTP, SSE, WebSocket, or OAuth. Attach individual tools to agents from each agent’s MCP Servers step.',
}: Props) {
  const { toast } = useToast()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<StatusFilter>('all')
  const { data, loading, refetch } = useMcpServers(page, 20, {
    search: search || undefined,
    status: filter === 'all' ? undefined : filter,
  })
  const { data: agentsData } = useAgents(1, undefined, undefined, 100)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [actionId, setActionId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<McpServerPublic | null>(null)

  const agentMap = new Map((agentsData?.items ?? []).map(a => [a.id!, a.name]))

  const servers = data?.items ?? []

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handleFilterChange = (f: StatusFilter) => {
    setFilter(f)
    setPage(1)
  }

  const handleDiscover = async (server: McpServerPublic) => {
    if (!server.id) return
    setActionId(server.id)
    try {
      await mcpApi.discover(server.id)
      toast.success('Tools refreshed')
      refetch()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Refresh failed')
    } finally {
      setActionId(null)
    }
  }

  const handleToggle = async (server: McpServerPublic) => {
    if (!server.id) return
    setActionId(server.id)
    try {
      await mcpApi.update(server.id, { is_active: !server.is_active })
      toast.success(server.is_active ? 'Server disabled' : 'Server enabled')
      refetch()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Update failed')
    } finally {
      setActionId(null)
    }
  }

  const handleDeleteConfirmed = async () => {
    const server = deleteTarget
    if (!server?.id) return
    setActionId(server.id)
    try {
      await mcpApi.delete(server.id)
      toast.success('Server removed')
      setDeleteTarget(null)
      refetch()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setActionId(null)
    }
  }

  const columns = [
    {
      key: 'name',
      header: 'Server',
      render: (row: McpServerPublic) => (
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium truncate">
              {row.name || row.user_description || row.connection_string?.split('/').pop() || 'Unnamed'}
            </span>
            {row.registry_key && (
              <Badge variant="primary" className="text-[10px] shrink-0">catalog</Badge>
            )}
            {!row.is_active && (
              <Badge variant="neutral" className="text-[10px] shrink-0">disabled</Badge>
            )}
          </div>
          {row.connection_string && (
            <p className="text-[11px] font-mono text-[var(--text-3)] truncate max-w-[220px] mt-0.5">
              {row.connection_string}
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'agent',
      header: 'Legacy agent',
      render: (row: McpServerPublic) => {
        if (!row.agent_id) {
          return <span className="text-[13px] text-[var(--text-3)] italic">Standalone</span>
        }
        const name = agentMap.get(row.agent_id)
        return (
          <div className="flex items-center gap-1.5 text-[13px] text-[var(--text-2)]">
            <Bot className="w-3.5 h-3.5 text-[var(--text-3)] shrink-0" />
            <span className="truncate max-w-[120px]">{name ?? row.agent_id.slice(0, 8) + '…'}</span>
          </div>
        )
      },
    },
    {
      key: 'transport',
      header: 'Transport',
      render: (row: McpServerPublic) => (
        <McpTransportBadge transport={row.transport} authType={row.auth_type} />
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: McpServerPublic) => (
        <div className="space-y-1">
          <McpStatusBadge status={row.status} />
          {row.status === 'error' && row.last_error && (
            <div className="flex items-center gap-1 text-[11px] text-red-600 dark:text-red-400">
              <AlertCircle className="w-3 h-3 shrink-0" />
              <span className="truncate max-w-[140px]">{row.last_error}</span>
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'tools',
      header: 'Tools',
      render: (row: McpServerPublic) => (
        <div className="flex items-center gap-1.5 text-[13px]">
          <Wrench className="w-3.5 h-3.5 text-[var(--text-3)]" />
          <span>{row.tool_count}</span>
        </div>
      ),
    },
    {
      key: 'discovered',
      header: 'Last discovered',
      render: (row: McpServerPublic) => (
        <span className="text-[12px] text-[var(--text-3)]">
          {row.discovered_at ? formatDate(row.discovered_at) : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: McpServerPublic) => {
        const busy = actionId === row.id
        return (
          <div className="flex items-center gap-1 justify-end">
            <Button
              variant="ghost" size="xs"
              onClick={() => handleDiscover(row)}
              disabled={busy}
              title="Refresh tools"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="ghost" size="xs"
              onClick={() => handleToggle(row)}
              disabled={busy}
              title={row.is_active ? 'Disable' : 'Enable'}
            >
              {row.is_active
                ? <ToggleRight className="w-4 h-4 text-green-500" />
                : <ToggleLeft className="w-4 h-4 text-[var(--text-3)]" />
              }
            </Button>
            <Button
              variant="ghost" size="xs"
              onClick={() => setDeleteTarget(row)}
              disabled={busy}
              className="hover:text-red-500"
              title="Delete"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={
          <Button variant="primary" size="sm" onClick={() => setSheetOpen(true)} className="gap-2">
            <Plug className="w-4 h-4" />
            Connect Server
          </Button>
        }
      />

      <McpInfoCard
        title="How connecting an MCP server works"
        steps={[
          'Connect a server here — paste a URL/command or pick one from the catalog. You don’t need to pick an agent; a server can just sit here connected, ready for any agent to use.',
          'Open any agent’s Edit page → MCP Servers step. Every server connected here shows up there too — same data, same list.',
          'Expand a server in that step and check off exactly which of its tools that agent should have. Different agents can pick different tools from the same server.',
          'To remove just one agent’s access, use the unplug icon on that agent’s MCP Servers step — it keeps the server connected for everyone else. Deleting a server here (trash icon) disconnects it everywhere, for every agent.',
        ]}
      />

      {/* Search + status filter tabs */}
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search servers..."
          className="max-w-[240px]"
        />

        <div className="flex items-center gap-1 flex-wrap">
          {(['all', 'connected', 'error', 'pending'] as StatusFilter[]).map(f => (
            <button
              key={f}
              type="button"
              onClick={() => handleFilterChange(f)}
              className={
                'px-3 py-1.5 rounded-lg text-[13px] font-medium capitalize transition-colors ' +
                (filter === f
                  ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300'
                  : 'text-[var(--text-3)] hover:text-[var(--text-1)]')
              }
            >
              {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="glass rounded-[var(--radius-lg)] overflow-hidden">
        <DataTable
          columns={columns}
          data={servers}
          isLoading={loading}
          emptyIcon={Plug}
          emptyMessage="No MCP servers connected"
          emptyDescription="Connect an MCP server from the catalog or paste a custom connection string."
          emptyAction={
            <Button variant="primary" size="sm" onClick={() => setSheetOpen(true)} className="gap-2">
              <Plug className="w-4 h-4" />
              Connect Server
            </Button>
          }
          pagination={data && data.total_pages > 1 ? {
            page: data.page,
            pageSize: data.page_size,
            total: data.total,
            onPageChange: setPage,
          } : undefined}
        />
      </div>

      <ConnectMcpSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        onSuccess={refetch}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={open => { if (!open) setDeleteTarget(null) }}
        title="Delete MCP server?"
        description={
          <>
            Delete <span className="font-medium text-[var(--text-1)]">
              {deleteTarget?.name || deleteTarget?.connection_string}
            </span>? This disconnects it for every agent it&apos;s attached to — not just one.
          </>
        }
        confirmLabel="Delete"
        loading={actionId === deleteTarget?.id}
        onConfirm={handleDeleteConfirmed}
      />
    </>
  )
}
