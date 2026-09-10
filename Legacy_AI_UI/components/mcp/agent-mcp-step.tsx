'use client'

import { useState, useMemo } from 'react'
import { Plug, Unplug, Trash2, RefreshCw, Wrench, AlertCircle, Loader2, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { McpStatusBadge, McpTransportBadge } from '@/components/mcp/mcp-status-badge'
import { ConnectMcpSheet } from '@/components/mcp/connect-mcp-sheet'
import { McpInfoCard } from '@/components/mcp/mcp-info-card'
import { useMcpServers, useAgentMcpTools } from '@/hooks/use-mcp-servers'
import { mcpApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import type { McpServerPublic } from '@/types'
import { cn } from '@/lib/utils'

interface Props {
  agentId: string
}

export function AgentMcpStep({ agentId }: Props) {
  const { toast } = useToast()
  // Every MCP server connected in the org — a server no longer belongs to one
  // agent, so any of them can have individual tools attached here.
  const { data: serversPage, loading: serversLoading, refetch: refetchServers } = useMcpServers(1, 100)
  const servers = serversPage?.items ?? []
  const { data: attachedTools, loading: attachedLoading, refetch: refetchAttached } = useAgentMcpTools(agentId)

  const [sheetOpen, setSheetOpen] = useState(false)
  const [actionId, setActionId] = useState<string | null>(null)
  const [pendingTool, setPendingTool] = useState<string | null>(null) // `${serverId}:${toolName}`
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [deleteTarget, setDeleteTarget] = useState<McpServerPublic | null>(null)
  const [detachAllTarget, setDetachAllTarget] = useState<McpServerPublic | null>(null)
  const [detachAllBusy, setDetachAllBusy] = useState(false)

  const attachedByServer = useMemo(() => {
    const map = new Map<string, Set<string>>()
    for (const t of attachedTools) {
      if (!map.has(t.mcp_server_id)) map.set(t.mcp_server_id, new Set())
      map.get(t.mcp_server_id)!.add(t.tool_name)
    }
    return map
  }, [attachedTools])

  const loading = serversLoading || attachedLoading

  const toggleExpanded = (serverId: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(serverId)) next.delete(serverId)
      else next.add(serverId)
      return next
    })
  }

  const toggleTool = async (server: McpServerPublic, toolName: string, currentlyAttached: boolean) => {
    if (!server.id) return
    const key = `${server.id}:${toolName}`
    setPendingTool(key)
    try {
      if (currentlyAttached) {
        await mcpApi.detachTool(server.id, agentId, toolName)
      } else {
        await mcpApi.attachTools(server.id, agentId, [toolName])
      }
      refetchAttached()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to update tool attachment')
    } finally {
      setPendingTool(null)
    }
  }

  const selectAllTools = async (server: McpServerPublic, attached: Set<string>) => {
    if (!server.id) return
    const missing = server.tools.map(t => t.name).filter(n => !attached.has(n))
    if (missing.length === 0) return
    setPendingTool(`${server.id}:__all__`)
    try {
      await mcpApi.attachTools(server.id, agentId, missing)
      refetchAttached()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to attach all tools')
    } finally {
      setPendingTool(null)
    }
  }

  const deselectAllTools = async (server: McpServerPublic, attached: Set<string>) => {
    if (!server.id || attached.size === 0) return
    setPendingTool(`${server.id}:__all__`)
    try {
      await Promise.all([...attached].map(name => mcpApi.detachTool(server.id!, agentId, name)))
      refetchAttached()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to detach all tools')
    } finally {
      setPendingTool(null)
    }
  }

  const handleDetachAllConfirmed = async () => {
    const server = detachAllTarget
    if (!server?.id) return
    const attached = attachedByServer.get(server.id) ?? new Set<string>()
    setDetachAllBusy(true)
    try {
      await Promise.all([...attached].map(name => mcpApi.detachTool(server.id!, agentId, name)))
      toast.success('Disconnected from this agent')
      setDetachAllTarget(null)
      refetchAttached()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to disconnect')
    } finally {
      setDetachAllBusy(false)
    }
  }

  const handleDiscover = async (server: McpServerPublic) => {
    if (!server.id) return
    setActionId(server.id)
    try {
      await mcpApi.discover(server.id)
      toast.success('Tools refreshed')
      refetchServers()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Refresh failed')
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
      refetchServers()
      refetchAttached()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Remove failed')
    } finally {
      setActionId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold">MCP Servers</h3>
          <p className="text-[13px] text-[var(--text-3)] mt-0.5">
            Pick which tools from any connected MCP server this agent can use.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setSheetOpen(true)} className="gap-2 shrink-0">
          <Plug className="w-4 h-4" />
          Connect Server
        </Button>
      </div>

      <McpInfoCard
        title="How this step works"
        defaultOpen={servers.length === 0}
        steps={[
          'Every MCP server your organization has connected shows up below — not just ones you connect from here.',
          'Expand a server (chevron on the left) to see its individual tools, and check exactly which ones this agent should have.',
          'Only checked tools are usable by this agent — connecting a server doesn’t grant it every tool automatically.',
          'The unplug icon detaches all of this agent’s tools from that server without touching any other agent; the trash icon deletes the server entirely, for everyone.',
        ]}
      />

      {loading ? (
        <div className="flex items-center justify-center py-10 text-[var(--text-3)]">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : servers.length === 0 ? (
        <div className="border border-dashed border-[var(--border-2)] rounded-[var(--radius-lg)] p-8 text-center">
          <Plug className="w-8 h-8 text-[var(--text-3)] mx-auto mb-3" />
          <p className="text-[14px] font-medium text-[var(--text-2)]">No MCP servers connected</p>
          <p className="text-[13px] text-[var(--text-3)] mt-1 mb-4">
            Connect a server, then choose which of its tools this agent can use.
          </p>
          <Button variant="secondary" size="sm" onClick={() => setSheetOpen(true)} className="gap-2">
            <Plug className="w-4 h-4" />
            Connect Server
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {servers.map(server => {
            const busy = actionId === server.id
            const isOpen = expanded.has(server.id!)
            const displayName = server.name || server.user_description || server.connection_string?.split('/').pop() || 'Unnamed'
            const attached = attachedByServer.get(server.id!) ?? new Set<string>()
            return (
              <div
                key={server.id}
                className="glass rounded-[var(--radius-lg)] overflow-hidden"
              >
                <div className="flex items-start gap-4 p-4">
                  <button
                    type="button"
                    onClick={() => toggleExpanded(server.id!)}
                    className="mt-0.5 shrink-0 text-[var(--text-3)] hover:text-[var(--text-1)]"
                    disabled={server.tool_count === 0}
                    title={isOpen ? 'Collapse' : 'Choose tools'}
                  >
                    {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </button>

                  <div className="flex-1 min-w-0 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[14px] font-medium">{displayName}</span>
                      {server.registry_key && (
                        <Badge variant="primary" className="text-[10px]">catalog</Badge>
                      )}
                      <McpStatusBadge status={server.status} />
                      <McpTransportBadge transport={server.transport} authType={server.auth_type} />
                      {attached.size > 0 && (
                        <Badge variant="info" className="text-[10px]">
                          {attached.size} tool{attached.size !== 1 ? 's' : ''} attached
                        </Badge>
                      )}
                    </div>

                    {server.connection_string && (
                      <p className="text-[11px] font-mono text-[var(--text-3)] truncate">
                        {server.connection_string}
                      </p>
                    )}

                    {server.status === 'error' && server.last_error && (
                      <div className="flex items-center gap-1 text-[11px] text-red-600 dark:text-red-400">
                        <AlertCircle className="w-3 h-3 shrink-0" />
                        <span className="truncate">{server.last_error}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant="ghost" size="xs"
                      onClick={() => handleDiscover(server)}
                      disabled={busy}
                      title="Refresh tools"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} />
                    </Button>
                    <Button
                      variant="ghost" size="xs"
                      onClick={() => setDetachAllTarget(server)}
                      disabled={busy || attached.size === 0}
                      className="hover:text-amber-500"
                      title="Disconnect from this agent (detach all its tools here, keep the server connected for others)"
                    >
                      <Unplug className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost" size="xs"
                      onClick={() => setDeleteTarget(server)}
                      disabled={busy}
                      className="hover:text-red-500"
                      title="Delete server entirely (disconnects it for every agent)"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>

                {isOpen && server.tool_count > 0 && (
                  <div className="border-t border-[var(--border)] bg-[var(--surface-2)] p-3 space-y-1">
                    {(() => {
                      const allPending = pendingTool === `${server.id}:__all__`
                      const allSelected = attached.size === server.tool_count
                      return (
                        <div className="flex items-center justify-between px-2.5 pb-2 mb-1 border-b border-[var(--border)]">
                          <span className="text-[11px] text-[var(--text-3)]">
                            {attached.size} of {server.tool_count} selected
                          </span>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost" size="xs"
                              onClick={() => selectAllTools(server, attached)}
                              disabled={allPending || allSelected}
                              className="h-6 text-[11.5px] px-2"
                            >
                              {allPending && !allSelected ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                              Select all
                            </Button>
                            <Button
                              variant="ghost" size="xs"
                              onClick={() => deselectAllTools(server, attached)}
                              disabled={allPending || attached.size === 0}
                              className="h-6 text-[11.5px] px-2"
                            >
                              {allPending && attached.size > 0 ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                              Clear all
                            </Button>
                          </div>
                        </div>
                      )
                    })()}
                    {server.tools.map(tool => {
                      const isAttached = attached.has(tool.name)
                      const isPending = pendingTool === `${server.id}:${tool.name}`
                      return (
                        <label
                          key={tool.name}
                          className={cn(
                            'flex items-start gap-3 p-2.5 rounded-[var(--radius-md)] cursor-pointer transition-colors',
                            isAttached ? 'bg-violet-500/5' : 'hover:bg-[var(--surface)]',
                            isPending && 'opacity-60 pointer-events-none',
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={isAttached}
                            onChange={() => toggleTool(server, tool.name, isAttached)}
                            className="mt-1 w-4 h-4 accent-violet-600"
                          />
                          <Wrench className="w-4 h-4 text-violet-600 dark:text-violet-400 mt-0.5 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <span className="text-[13px] font-mono font-medium">{tool.name}</span>
                            {tool.description && (
                              <p className="text-[12px] text-[var(--text-3)] mt-0.5">{tool.description}</p>
                            )}
                          </div>
                          {isPending && <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0 mt-1" />}
                        </label>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <ConnectMcpSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        onSuccess={() => { refetchServers(); refetchAttached() }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={open => { if (!open) setDeleteTarget(null) }}
        title="Remove MCP server?"
        description={
          <>
            Remove <span className="font-medium text-[var(--text-1)]">
              {deleteTarget?.name || deleteTarget?.connection_string}
            </span>? This disconnects it for every agent it&apos;s attached to, not just this one.
          </>
        }
        confirmLabel="Remove"
        loading={actionId === deleteTarget?.id}
        onConfirm={handleDeleteConfirmed}
      />

      <ConfirmDialog
        open={!!detachAllTarget}
        onOpenChange={open => { if (!open) setDetachAllTarget(null) }}
        title="Disconnect from this agent?"
        description={
          <>
            Detach all {detachAllTarget ? (attachedByServer.get(detachAllTarget.id!)?.size ?? 0) : 0} attached tool(s) of{' '}
            <span className="font-medium text-[var(--text-1)]">
              {detachAllTarget?.name || detachAllTarget?.connection_string}
            </span> from this agent. The server itself stays connected — other agents keep whatever tools they have.
          </>
        }
        confirmLabel="Disconnect"
        loading={detachAllBusy}
        onConfirm={handleDetachAllConfirmed}
      />
    </div>
  )
}
