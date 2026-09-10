'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Package, Edit2, Trash2, SlidersHorizontal } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { CreateButton } from '@/components/ui/create-button'
import { DataTable, type SortState } from '@/components/ui/data-table'
import { BulkDeleteButton } from '@/components/ui/bulk-delete-button'
import { Pagination } from '@/components/ui/pagination'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/search-input'
import { Select } from '@/components/ui/select'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { EmptyState } from '@/components/ui/empty-state'
import { Dialog } from '@/components/ui/dialog'
import { useToolRegistry } from '@/hooks/use-tool-registry'
import { useBulkDelete } from '@/hooks/use-bulk-delete'
import { toolRegistryApi, type ToolRegistryListFilters } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import type { ToolRegistryPublic } from '@/types'
import { formatDate } from '@/lib/utils'

const typeVariant: Record<string, 'primary' | 'warning' | 'info' | 'neutral'> = {
  db: 'warning',
  http: 'info',
  rag: 'primary',
  custom: 'neutral',
}

export default function AdminToolRegistryPage() {
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'db' | 'http' | 'rag' | 'custom'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [deleteTarget, setDeleteTarget] = useState<ToolRegistryPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<{ ids: string[]; clear: () => void } | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [sort, setSort] = useState<SortState>(null)

  const filters: ToolRegistryListFilters = {
    search: search || undefined,
    type: typeFilter === 'all' ? undefined : typeFilter,
    isActive: statusFilter === 'all' ? undefined : statusFilter === 'active',
    sortBy: (sort?.key as ToolRegistryListFilters['sortBy']) ?? undefined,
    sortOrder: sort?.dir,
  }

  const { data, loading, error, refetch } = useToolRegistry(page, pageSize, filters)
  const { toast } = useToast()
  const bulkDelete = useBulkDelete(id => toolRegistryApi.delete(id), { entity: 'tool type', onDone: refetch })

  const items = data?.items ?? []

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handleTypeChange = (val: typeof typeFilter) => {
    setTypeFilter(val)
    setPage(1)
  }

  const handleStatusChange = (val: typeof statusFilter) => {
    setStatusFilter(val)
    setPage(1)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await toolRegistryApi.delete(deleteTarget.id!)
      toast.success('Tool deleted')
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

  const columns = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      sortAccessor: (row: ToolRegistryPublic) => row.name,
      render: (row: ToolRegistryPublic) => (
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-violet-600 dark:text-violet-400 shrink-0" />
          <span className="text-[14px] font-medium">{row.name}</span>
        </div>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (row: ToolRegistryPublic) => (
        <Badge variant={typeVariant[row.type] ?? 'neutral'} className="capitalize">{row.type}</Badge>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (row: ToolRegistryPublic) => (
        <span className="text-[13px] text-[var(--text-3)]">{row.description ?? '—'}</span>
      ),
    },
    {
      key: 'schema',
      header: 'Schema',
      render: (row: ToolRegistryPublic) =>
        row.tool_schema
          ? <Badge variant="success">Has schema</Badge>
          : <Badge variant="neutral">No schema</Badge>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: ToolRegistryPublic) => (
        <StatusIndicator status={row.is_active ? 'active' : 'inactive'} label={row.is_active ? 'Active' : 'Inactive'} />
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      sortAccessor: (row: ToolRegistryPublic) => row.created_at ?? '',
      render: (row: ToolRegistryPublic) => (
        <span className="text-[12px] text-[var(--text-3)]">{formatDate(row.created_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: ToolRegistryPublic) => (
        <div className="flex gap-1">
          <Link href={`/admin/tool-registry/${row.id}/edit`}>
            <Button variant="ghost" size="xs">
              <Edit2 className="w-3.5 h-3.5" />
            </Button>
          </Link>
          <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)} className="text-red-500 dark:text-red-400 hover:bg-red-500/10">
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      ),
    },
  ]

  const isFiltering = !!search.trim() || typeFilter !== 'all' || statusFilter !== 'all'

  const resetFilters = () => {
    setSearch('')
    setTypeFilter('all')
    setStatusFilter('all')
    setPage(1)
  }

  return (
    <>
      <PageHeader
        title="Tool Registry"
        description="Global catalog of available tool implementations"
        actions={
          <Link href="/admin/tool-registry/create">
            <CreateButton size="sm">Add Tool Type</CreateButton>
          </Link>
        }
      />

      {/* Search + filters */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search registry..."
          className="max-w-[260px]"
        />

        <Select
          value={typeFilter}
          onValueChange={v => handleTypeChange(v as typeof typeFilter)}
          className="w-36"
          options={[
            { value: 'all', label: 'All types' },
            { value: 'db', label: 'Database' },
            { value: 'http', label: 'HTTP' },
            { value: 'rag', label: 'RAG' },
            { value: 'custom', label: 'Custom' },
          ]}
        />

        <Select
          value={statusFilter}
          onValueChange={v => handleStatusChange(v as typeof statusFilter)}
          className="w-36"
          options={[
            { value: 'all', label: 'All statuses' },
            { value: 'active', label: 'Active' },
            { value: 'inactive', label: 'Inactive' },
          ]}
        />

        {isFiltering && (
          <button
            onClick={resetFilters}
            className="text-[13px] text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {error ? (
        <DataTable columns={columns} data={[]} error={error} onRetry={refetch} />
      ) : !loading && items.length === 0 ? (
        isFiltering ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <SlidersHorizontal className="w-10 h-10 text-[var(--text-3)] mb-3" />
            <p className="text-[15px] font-medium">No results match your filters</p>
            <Button variant="ghost" size="sm" className="mt-4" onClick={resetFilters}>
              Clear filters
            </Button>
          </div>
        ) : (
          <EmptyState
            icon={Package}
            title="No tool types yet"
            description="Add tool implementations to the registry so users can connect them."
            action={
              <Link href="/admin/tool-registry/create">
                <CreateButton size="sm">Add Tool Type</CreateButton>
              </Link>
            }
          />
        )
      ) : (
        <>
          <DataTable
            columns={columns}
            data={items}
            isLoading={loading}
            getRowId={row => row.id!}
            sortState={sort}
            onSortChange={next => { setSort(next); setPage(1) }}
            bulkActions={({ ids, clear }) => (
              <BulkDeleteButton
                count={ids.length}
                busy={bulkDelete.busy}
                label="Remove"
                busyLabel="Removing…"
                onClick={() => setBulkDeleteTarget({ ids, clear })}
              />
            )}
          />
          {data && data.total > pageSize && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.total}
              onPageChange={setPage}
              onPageSizeChange={s => { setPageSize(s); setPage(1) }}
            />
          )}
        </>
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Remove tool type?"
        footer={
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" size="sm" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" size="sm" onClick={handleDelete} disabled={deleting}>
              {deleting ? 'Removing…' : 'Remove'}
            </Button>
          </div>
        }
      >
        <p className="text-[13px] text-[var(--text-3)]">
          "<span className="text-[var(--text-1)]">{deleteTarget?.name}</span>" will be removed from the registry.
        </p>
      </Dialog>

      <Dialog
        open={!!bulkDeleteTarget}
        onOpenChange={open => !open && setBulkDeleteTarget(null)}
        title="Remove tool types?"
        footer={
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" size="sm" onClick={() => setBulkDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" size="sm" onClick={handleBulkDelete} disabled={bulkDelete.busy}>
              {bulkDelete.busy ? 'Removing…' : 'Remove'}
            </Button>
          </div>
        }
      >
        <p className="text-[13px] text-[var(--text-3)]">
          The <strong className="text-[var(--text-1)]">{bulkDeleteTarget?.ids.length}</strong> selected tool type{bulkDeleteTarget?.ids.length === 1 ? '' : 's'} will be removed from the registry.
        </p>
      </Dialog>
    </>
  )
}
