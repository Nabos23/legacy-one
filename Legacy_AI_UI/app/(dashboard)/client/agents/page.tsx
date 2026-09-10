'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  LayoutGrid,
  Table2,
  Edit2,
  Trash2,
  MessageSquare,
  Power,
  PenLine,
  Sparkles,
  ArrowRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { SlidersHorizontal } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { PageLoader } from '@/components/ui/loader'
import { DataTable, type Column, type SortState } from '@/components/ui/data-table'
import { BulkDeleteButton } from '@/components/ui/bulk-delete-button'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { EmptyState } from '@/components/ui/empty-state'
import { Pagination } from '@/components/ui/pagination'
import { Dialog } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { Bot } from 'lucide-react'
import { useAgents, type UseAgentsFilters } from '@/hooks/use-agents'
import { useBulkDelete } from '@/hooks/use-bulk-delete'
import { useToast } from '@/hooks/use-toast'
import { agentsApi } from '@/lib/api'
import { formatDate, truncate, stripMarkdown, agentVisibilityLabel } from '@/lib/utils'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import { ConnectorLogo } from '@/components/connectors/connector-logo'
import { useAuth } from '@/contexts/auth-context'
import type { AgentPublic } from '@/types'

type StatusFilter = 'all' | 'active' | 'inactive'
type CapabilityFilter = 'all' | 'has' | 'none'

export default function AgentsPage() {
  const [view, setView] = useState<'grid' | 'table'>('grid')
  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(10)
  const [deleteTarget, setDeleteTarget] = useState<AgentPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<{ ids: string[]; clear: () => void } | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [createChoiceOpen, setCreateChoiceOpen] = useState(false)

  // Filters — resolved server-side via useAgents, not client-side re-filtering
  // of whatever page happens to already be loaded.
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [toolsFilter, setToolsFilter] = useState<CapabilityFilter>('all')
  const [connectorsFilter, setConnectorsFilter] = useState<CapabilityFilter>('all')
  const [sort, setSort] = useState<SortState>(null)

  const capabilityToBool = (f: CapabilityFilter): boolean | undefined =>
    f === 'has' ? true : f === 'none' ? false : undefined

  const filters: UseAgentsFilters = {
    isActive: statusFilter === 'all' ? undefined : statusFilter === 'active',
    hasTools: capabilityToBool(toolsFilter),
    hasConnectors: capabilityToBool(connectorsFilter),
    sortBy: (sort?.key as UseAgentsFilters['sortBy']) ?? undefined,
    sortOrder: sort?.dir,
  }

  const { data, loading, error, refetch, updateLocal, page, setPage } = useAgents(
    1,
    undefined,
    search,
    pageSize,
    filters,
  )
  const { permissions } = useAuth()
  const { toast } = useToast()
  const bulkDelete = useBulkDelete(id => agentsApi.delete(id), { entity: 'agent', onDone: refetch })

  const agents = data?.items ?? []

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const resetFilters = () => {
    setStatusFilter('all')
    setToolsFilter('all')
    setConnectorsFilter('all')
    setPage(1)
  }

  const isFilteringByFacet = statusFilter !== 'all' || toolsFilter !== 'all' || connectorsFilter !== 'all'

  const handleToggleStatus = async (agent: AgentPublic) => {
    const wasActive = agent.is_active !== false
    // Optimistic: flip instantly so it feels like a toggle, not a network call;
    // roll back to `wasActive` only if the request actually fails.
    updateLocal(agent.id!, { is_active: !wasActive })
    setTogglingId(agent.id!)
    try {
      await agentsApi.toggleStatus(agent.id!, !wasActive)
    } catch (err) {
      updateLocal(agent.id!, { is_active: wasActive })
      toast.error(err instanceof Error ? err.message : 'Failed to update status')
    } finally {
      setTogglingId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await agentsApi.delete(deleteTarget.id!)
      toast.success(`Deleted agent ${deleteTarget.name}`)
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete agent')
    } finally {
      setDeleting(false)
    }
  }

  const handleBulkDelete = async () => {
    if (!bulkDeleteTarget) return
    try {
      await bulkDelete.run(bulkDeleteTarget.ids, bulkDeleteTarget.clear)
    } finally {
      setBulkDeleteTarget(null)
    }
  }

  const columns: Column<AgentPublic>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      sortAccessor: row => row.name,
      render: row => (
        <div className="flex items-center gap-2">
          <AgentAvatar
            name={row.name}
            avatarType={row.avatar_type}
            avatarValue={row.avatar_value}
            avatarUrl={row.avatar_url}
            size="sm"
          />
          {row.name}
        </div>
      ),
    },
    {
      key: 'is_active',
      header: 'Status',
      sortable: true,
      render: row => (
        <div className="flex items-center gap-2">
          <StatusIndicator status={row.is_active !== false ? 'active' : 'inactive'} />
          <Badge variant={row.is_active !== false ? 'success' : 'neutral'}>
            {row.is_active !== false ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      ),
    },
    {
      key: 'owner_scope',
      header: 'Visibility',
      render: row => (
        <Badge variant={row.owner_scope === 'organization' ? 'info' : 'neutral'}>
          {agentVisibilityLabel(row)}
        </Badge>
      ),
    },
    {
      key: 'connectors',
      header: 'Connectors',
      render: row => (
        <div className="flex items-center gap-1">
          {row.connectors && row.connectors.length > 0 ? (
            row.connectors.map(conn => (
              <ConnectorLogo
                key={conn.id}
                providerId={conn.provider_id}
                size="sm"
                className="w-5 h-5 rounded-md"
              />
            ))
          ) : (
            <span className="text-[12px] text-[var(--text-3)]">—</span>
          )}
        </div>
      ),
    },
    {
      key: 'prompt',
      header: 'System Prompt',
      render: row => (
        <span className="text-[12px] font-mono text-[var(--text-3)]">
          {truncate(row.prompt ?? '', 60)}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      sortAccessor: row => row.created_at ?? '',
      render: row => formatDate(row.created_at),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: row => (
        <div className="flex items-center gap-1">
          <Link href={`/client/playground?agent=${row.id}`}>
            <Button variant="ghost" size="xs">
              <MessageSquare className="w-4 h-4" />
            </Button>
          </Link>
          {permissions.edit_agent && (
            <Link href={`/client/agents/${row.id}/edit`}>
              <Button variant="ghost" size="xs">
                <Edit2 className="w-4 h-4" />
              </Button>
            </Link>
          )}
          {permissions.edit_agent && (
            <Button
              variant="ghost"
              size="xs"
              disabled={togglingId === row.id}
              onClick={() => handleToggleStatus(row)}
              title={row.is_active !== false ? 'Deactivate' : 'Activate'}
            >
              <Power className={`w-4 h-4 ${row.is_active !== false ? 'text-green-500' : 'text-[var(--text-3)]'}`} />
            </Button>
          )}
          {permissions.delete_agent && (
            <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)}>
              <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
            </Button>
          )}
        </div>
      ),
    },
  ]

  const isFiltering = !!search.trim() || isFilteringByFacet

  const statusOptions = [
    { value: 'all', label: 'All statuses' },
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ]
  const capabilityOptions = (label: string) => [
    { value: 'all', label: `All (${label})` },
    { value: 'has', label: `Has ${label}` },
    { value: 'none', label: `No ${label}` },
  ]

  const withPageReset = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v)
    setPage(1)
  }

  return (
    <>
      <PageHeader
        title="Agents"
        description="Create and manage your AI agents"
        actions={
          permissions.create_agent ? (
            <CreateButton onClick={() => setCreateChoiceOpen(true)}>Create Agent</CreateButton>
          ) : undefined
        }
      />

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search agents..."
          className="max-w-[280px]"
        />
        <Select
          value={statusFilter}
          onValueChange={withPageReset(v => setStatusFilter(v as StatusFilter))}
          options={statusOptions}
          className="w-[140px]"
        />
        <Select
          value={toolsFilter}
          onValueChange={withPageReset(v => setToolsFilter(v as CapabilityFilter))}
          options={capabilityOptions('Tools')}
          className="w-[150px]"
        />
        <Select
          value={connectorsFilter}
          onValueChange={withPageReset(v => setConnectorsFilter(v as CapabilityFilter))}
          options={capabilityOptions('Connectors')}
          className="w-[170px]"
        />

        {isFiltering && (
          <button
            onClick={() => { handleSearchChange(''); resetFilters() }}
            className="text-[13px] text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 transition-colors"
          >
            Clear filters
          </button>
        )}
        <div className="flex gap-1 ml-auto">
          <Button
            variant={view === 'grid' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setView('grid')}
          >
            <LayoutGrid className="w-4 h-4" />
          </Button>
          <Button
            variant={view === 'table' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setView('table')}
          >
            <Table2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {error ? (
        <DataTable columns={columns} data={[]} error={error} onRetry={refetch} />
      ) : !loading && agents.length === 0 ? (
        isFiltering ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <SlidersHorizontal className="w-10 h-10 text-[var(--text-3)] mb-3" />
            <p className="text-[15px] font-medium">No agents match these filters</p>
            <Button variant="ghost" size="sm" className="mt-4" onClick={() => { handleSearchChange(''); resetFilters() }}>
              Clear filters
            </Button>
          </div>
        ) : (
          <EmptyState
            icon={Bot}
            title="No agents yet"
            description="Create your first agent to get started"
            action={
              permissions.create_agent ? (
                <CreateButton onClick={() => setCreateChoiceOpen(true)}>Create Agent</CreateButton>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          {view === 'table' ? (
            <DataTable
              columns={columns}
              data={agents}
              isLoading={loading}
              getRowId={row => row.id!}
              sortState={sort}
              onSortChange={next => { setSort(next); setPage(1) }}
              bulkActions={({ ids, clear }) => (
                <BulkDeleteButton count={ids.length} busy={bulkDelete.busy} onClick={() => setBulkDeleteTarget({ ids, clear })} />
              )}
            />
          ) : loading && agents.length === 0 ? (
            <PageLoader label="Loading agents…" className="min-h-[40vh]" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map(agent => (
                <div
                  key={agent.id}
                  className="glass glass-hover p-5 rounded-[var(--radius-lg)] relative"
                >
                  <button
                    className="absolute top-4 right-4"
                    disabled={togglingId === agent.id}
                    onClick={() => handleToggleStatus(agent)}
                    title={agent.is_active !== false ? 'Click to deactivate' : 'Click to activate'}
                  >
                    <Badge variant={agent.is_active !== false ? 'success' : 'neutral'}>
                      {agent.is_active !== false ? 'Active' : 'Inactive'}
                    </Badge>
                  </button>
                  <AgentAvatar
                    name={agent.name}
                    avatarType={agent.avatar_type}
                    avatarValue={agent.avatar_value}
                    avatarUrl={agent.avatar_url}
                    size="md"
                  />
                  <h3 className="text-[16px] font-semibold mt-3">{agent.name}</h3>
                  {agent.model && (
                    <Badge variant="info" className="mt-2 normal-case">{agent.model}</Badge>
                  )}
                  <div className="flex items-center gap-1.5 flex-wrap mt-2">
                    <Badge variant={agent.owner_scope === 'organization' ? 'info' : 'neutral'}>
                      {agentVisibilityLabel(agent)}
                    </Badge>
                    {agent.connectors && agent.connectors.length > 0 && (
                      <div className="flex items-center gap-1 ml-1" title={`Connected services: ${agent.connectors.map(c => c.name).join(', ')}`}>
                        {agent.connectors.map(conn => (
                          <ConnectorLogo
                            key={conn.id}
                            providerId={conn.provider_id}
                            size="sm"
                            className="w-5 h-5 rounded-md"
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="text-[13px] text-[var(--text-3)] mt-2 line-clamp-2">
                    {agent.description || (agent.prompt ? stripMarkdown(agent.prompt) : '—')}
                  </p>
                  <Separator className="my-3" />
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-[var(--text-3)]">
                      {formatDate(agent.created_at)}
                    </span>
                    <div className="flex gap-1">
                      <Link href={`/client/playground?agent=${agent.id}`}>
                        <Button variant="ghost" size="xs">
                          <MessageSquare className="w-4 h-4" />
                        </Button>
                      </Link>
                      <Link href={`/client/agents/${agent.id}/edit`}>
                        <Button variant="ghost" size="xs"><Edit2 className="w-4 h-4" /></Button>
                      </Link>
                      <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(agent)}>
                        <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {data && data.total > pageSize && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.total}
              onPageChange={setPage}
              pageSizeOptions={[5, 10, 20, 50]}
              onPageSizeChange={s => { setPageSize(s); setPage(1) }}
            />
          )}
        </>
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Delete Agent"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>
              Delete
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Are you sure you want to delete{' '}
          <strong>{deleteTarget?.name}</strong>? This action cannot be undone.
        </p>
      </Dialog>

      <Dialog
        open={!!bulkDeleteTarget}
        onOpenChange={open => !open && setBulkDeleteTarget(null)}
        title="Delete Agents"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setBulkDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleBulkDelete} disabled={bulkDelete.busy}>Delete</Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Are you sure you want to delete the {bulkDeleteTarget?.ids.length} selected agent(s)? This action cannot be undone.
        </p>
      </Dialog>

      <Dialog
        open={createChoiceOpen}
        onOpenChange={setCreateChoiceOpen}
        title="Create an agent"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Link
            href="/client/agents/build"
            onClick={() => setCreateChoiceOpen(false)}
            className="group flex flex-col gap-3 rounded-2xl border border-[var(--border-1)] p-5 text-left transition-colors hover:border-violet-400 hover:bg-violet-500/5"
          >
            <div className="flex size-10 items-center justify-center rounded-xl bg-violet-500/10">
              <Sparkles className="size-5 text-violet-500" />
            </div>
            <div>
              <p className="flex items-center gap-1.5 font-semibold">
                With a prompt
                <ArrowRight className="size-3.5 text-[var(--text-3)] transition-transform group-hover:translate-x-0.5" />
              </p>
              <p className="mt-1 text-[13px] text-[var(--text-3)]">
                Describe what you want, and I&rsquo;ll ask questions, connect services, and build it for you.
              </p>
            </div>
          </Link>
          <Link
            href="/client/agents/create"
            onClick={() => setCreateChoiceOpen(false)}
            className="group flex flex-col gap-3 rounded-2xl border border-[var(--border-1)] p-5 text-left transition-colors hover:border-violet-400 hover:bg-violet-500/5"
          >
            <div className="flex size-10 items-center justify-center rounded-xl bg-violet-500/10">
              <PenLine className="size-5 text-violet-500" />
            </div>
            <div>
              <p className="flex items-center gap-1.5 font-semibold">
                Manually
                <ArrowRight className="size-3.5 text-[var(--text-3)] transition-transform group-hover:translate-x-0.5" />
              </p>
              <p className="mt-1 text-[13px] text-[var(--text-3)]">
                Set the name, system prompt, tools, and connectors yourself, step by step.
              </p>
            </div>
          </Link>
        </div>
      </Dialog>
    </>
  )
}
