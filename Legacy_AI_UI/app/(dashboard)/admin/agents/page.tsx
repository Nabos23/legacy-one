'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { Zap, Eye, Trash2, X, SlidersHorizontal, Power } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { PageHeader } from '@/components/ui/page-header'
import { DataTable, type Column, type SortState } from '@/components/ui/data-table'
import { BulkDeleteButton } from '@/components/ui/bulk-delete-button'
import { Select } from '@/components/ui/select'
import { Pagination } from '@/components/ui/pagination'
import { Badge } from '@/components/ui/badge'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { useAgents, type UseAgentsFilters } from '@/hooks/use-agents'
import { useBulkDelete } from '@/hooks/use-bulk-delete'
import { useOrganizations } from '@/hooks/use-organizations'
import { agentsApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import { formatDate, truncate, stripMarkdown, agentVisibilityLabel } from '@/lib/utils'
import type { AgentPublic } from '@/types'
import { useAuth } from '@/contexts/auth-context'
import { ConnectorLogo } from '@/components/connectors/connector-logo'

type StatusFilter = 'all' | 'active' | 'inactive'
type CapabilityFilter = 'all' | 'has' | 'none'

export default function AdminAgentsPage() {
  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(10)
  const [deleteTarget, setDeleteTarget] = useState<AgentPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<{ ids: string[]; clear: () => void } | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [orgFilter, setOrgFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [toolsFilter, setToolsFilter] = useState<CapabilityFilter>('all')
  const [connectorsFilter, setConnectorsFilter] = useState<CapabilityFilter>('all')
  const [mcpFilter, setMcpFilter] = useState<CapabilityFilter>('all')
  const [sort, setSort] = useState<SortState>(null)

  const capabilityToBool = (f: CapabilityFilter): boolean | undefined =>
    f === 'has' ? true : f === 'none' ? false : undefined

  const filters: UseAgentsFilters = {
    isActive: statusFilter === 'all' ? undefined : statusFilter === 'active',
    hasTools: capabilityToBool(toolsFilter),
    hasConnectors: capabilityToBool(connectorsFilter),
    hasMcp: capabilityToBool(mcpFilter),
    sortBy: (sort?.key as UseAgentsFilters['sortBy']) ?? undefined,
    sortOrder: sort?.dir,
  }

  const { data, loading, error, refetch, page, setPage, updateLocal } =
    useAgents(1, orgFilter || undefined, search, pageSize, filters)
  const { toast } = useToast()
  const { permissions } = useAuth()
  const { data: orgsData } = useOrganizations(1, undefined, 1000, {}, true)
  const orgNameMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const org of orgsData?.items ?? []) {
      if (org.id) map[org.id] = org.name
    }
    return map
  }, [orgsData?.items])
  const bulkDelete = useBulkDelete(id => agentsApi.delete(id), { entity: 'agent', onDone: refetch })

  const agents = data?.items ?? []

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const resetFilters = () => {
    setOrgFilter('')
    setStatusFilter('all')
    setToolsFilter('all')
    setConnectorsFilter('all')
    setMcpFilter('all')
    setPage(1)
  }

  const isFilteringByFacet =
    !!orgFilter || statusFilter !== 'all' || toolsFilter !== 'all' || connectorsFilter !== 'all' || mcpFilter !== 'all'

  const handleToggleStatus = async (agent: AgentPublic) => {
    const wasActive = agent.is_active !== false
    updateLocal(agent.id!, { is_active: !wasActive })
    setTogglingId(agent.id!)
    try {
      await agentsApi.toggleStatus(agent.id!, !wasActive)
    } catch (e: unknown) {
      updateLocal(agent.id!, { is_active: wasActive })
      toast.error(e instanceof Error ? e.message : 'Failed to update status')
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
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
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

  const baseColumns: Column<AgentPublic>[] = [
    {
      key: 'name',
      header: 'Agent Name',
      sortable: true,
      sortAccessor: row => row.name,
      render: row => (
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          <Link href={`/admin/agents/${row.id}`} className="font-medium hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
            {row.name}
          </Link>
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
      key: 'prompt',
      header: 'Description',
      render: row => (
        <span className="text-[12px] text-[var(--text-3)]">
          {truncate(row.description || (row.prompt ? stripMarkdown(row.prompt) : '—'), 60)}
        </span>
      ),
    },
    {
      key: 'tool_ids',
      header: 'Tools',
      render: row => (
        <Badge variant="neutral">{row.tool_ids?.length ?? 0}</Badge>
      ),
    },
  ]

  baseColumns.push({
    key: 'owner_scope',
    header: 'Visibility',
    render: row => (
      <Badge variant={row.owner_scope === 'organization' ? 'info' : 'neutral'}>
        {agentVisibilityLabel(row)}
      </Badge>
    ),
  })

  baseColumns.push({
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
  })

  if (permissions.is_super_admin) {
    baseColumns.push({
      key: 'organization_id',
      header: 'Organization',
      render: row => (
        <span className="text-[13px] text-[var(--text-2)]">
          {orgNameMap[row.organization_id] ?? row.organization_id.slice(-8)}
        </span>
      ),
    })
  }

  baseColumns.push(
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      sortAccessor: row => row.created_at ?? '',
      render: row => <span className="text-[13px] text-[var(--text-3)]">{formatDate(row.created_at)}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: row => (
        <div className="flex items-center gap-2">
          <Link href={`/admin/agents/${row.id}`}>
            <Button variant="ghost" size="xs">
              <Eye className="w-4 h-4" />
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="xs"
            disabled={togglingId === row.id}
            onClick={() => handleToggleStatus(row)}
            title={row.is_active !== false ? 'Deactivate' : 'Activate'}
          >
            <Power className={`w-4 h-4 ${row.is_active !== false ? 'text-green-500' : 'text-[var(--text-3)]'}`} />
          </Button>
          <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)}>
            <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
          </Button>
        </div>
      ),
    }
  )

  const columns = baseColumns

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
  const orgOptions = [
    { value: '', label: 'All organizations' },
    ...(orgsData?.items ?? []).map(o => ({ value: o.id!, label: o.name })),
  ]

  const withPageReset = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v)
    setPage(1)
  }

  return (
    <>
      <PageHeader
        title="Agents"
        description="Monitor and manage all agents across the system"
        actions={
          <Link href="/admin/agents/create">
            <CreateButton>New Agent</CreateButton>
          </Link>
        }
      />

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search agents..."
          className="max-w-[240px]"
          rightElement={search ? (
            <button
              type="button"
              onClick={() => handleSearchChange('')}
              className="text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          ) : undefined}
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
        <Select
          value={mcpFilter}
          onValueChange={withPageReset(v => setMcpFilter(v as CapabilityFilter))}
          options={capabilityOptions('MCP')}
          className="w-[150px]"
        />
        {permissions.is_super_admin && (
          <Select
            value={orgFilter}
            onValueChange={withPageReset(setOrgFilter)}
            options={orgOptions}
            className="w-[200px]"
          />
        )}

        {isFiltering && (
          <button
            onClick={() => { handleSearchChange(''); resetFilters() }}
            className="text-[13px] text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 transition-colors ml-auto"
          >
            Clear filters
          </button>
        )}
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
            icon={Zap}
            title="No agents yet"
            description="Create your first agent to get started"
            action={
              <Link href="/admin/agents/create">
                <CreateButton>Create Agent</CreateButton>
              </Link>
            }
          />
        )
      ) : (
        <>
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
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>Delete</Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Delete <strong>{deleteTarget?.name}</strong>? This cannot be undone.
        </p>
      </Dialog>

      <Dialog
        open={!!bulkDeleteTarget}
        onOpenChange={open => !open && setBulkDeleteTarget(null)}
        title="Delete Agents"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setBulkDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleBulkDelete} disabled={bulkDelete.busy}>
              {bulkDelete.busy ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Delete the <strong>{bulkDeleteTarget?.ids.length}</strong> selected agent{bulkDeleteTarget?.ids.length === 1 ? '' : 's'}? This cannot be undone.
        </p>
      </Dialog>
    </>
  )
}

