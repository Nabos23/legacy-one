'use client'

import { useState, useEffect } from 'react'
import { Building2, Trash2, SlidersHorizontal, Eye, Edit2 } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { PageHeader } from '@/components/ui/page-header'
import { DataTable, type Column, type SortState } from '@/components/ui/data-table'
import { BulkDeleteButton } from '@/components/ui/bulk-delete-button'
import { Pagination } from '@/components/ui/pagination'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { useOrganizations } from '@/hooks/use-organizations'
import { useBulkDelete } from '@/hooks/use-bulk-delete'
import { organizationsApi, usersApi, agentsApi, toolsApi, dbConnectionsApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import { formatDate } from '@/lib/utils'
import { useAuth } from '@/contexts/auth-context'
import type { OrganizationPublic } from '@/types'

export default function OrganizationsPage() {
  const [deleteTarget, setDeleteTarget] = useState<OrganizationPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<{ ids: string[]; clear: () => void } | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [pageSize, setPageSize] = useState(10)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const [sort, setSort] = useState<SortState>(null)
  const { data, loading, error, page, setPage, refetch } = useOrganizations(1, debouncedSearch, pageSize, {
    sortBy: (sort?.key as 'name' | 'created_at') ?? undefined,
    sortOrder: sort?.dir,
  })
  const { permissions } = useAuth()
  const { toast } = useToast()
  const bulkDelete = useBulkDelete(id => organizationsApi.delete(id), { entity: 'organization', onDone: refetch })

  // Search (name/description) is applied server-side, so the returned page is
  // already the filtered result — pagination totals stay accurate.
  const organizations = data?.items ?? []

  // Blast-radius: when a delete is pending, fetch how many dependent records exist.
  const [deleteCounts, setDeleteCounts] = useState<{ users: number; agents: number; tools: number; db: number } | null>(null)

  useEffect(() => {
    const id = deleteTarget?.id
    if (!id) {
      setDeleteCounts(null)
      return
    }
    let cancelled = false
    setDeleteCounts(null)
    const total = (r: PromiseSettledResult<{ total: number }>) => (r.status === 'fulfilled' ? r.value.total : 0)
    Promise.allSettled([
      usersApi.listByOrg(id, 1, 1),
      agentsApi.listByOrg(id, 1, 1),
      toolsApi.listByOrg(id, 1, 1),
      dbConnectionsApi.listByOrg(id, 1, 1),
    ]).then(([u, a, t, d]) => {
      if (cancelled) return
      setDeleteCounts({ users: total(u), agents: total(a), tools: total(t), db: total(d) })
    })
    return () => {
      cancelled = true
    }
  }, [deleteTarget])

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await organizationsApi.delete(deleteTarget.id!)
      toast.success(`Deleted ${deleteTarget.name}`)
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

  const columns: Column<OrganizationPublic>[] = [
    {
      key: 'name',
      header: 'Organization',
      sortable: true,
      sortAccessor: row => row.name,
      render: row => (
        <Link href={`/admin/organizations/${row.id}`} className="flex items-center gap-2 hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
          <Building2 className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          <span className="font-medium">{row.name}</span>
        </Link>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: row => (
        <span className="text-[13px] text-[var(--text-3)]">{row.description ?? '—'}</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      sortAccessor: row => row.created_at ?? '',
      render: row => <span className="text-[13px]">{formatDate(row.created_at)}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: () => <Badge variant="success">Active</Badge>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: row => (
        <div className="flex items-center gap-1">
          <Link href={`/admin/organizations/${row.id}`}>
            <Button variant="ghost" size="xs"><Eye className="w-4 h-4" /></Button>
          </Link>
          <Link href={`/admin/organizations/${row.id}/edit`}>
            <Button variant="ghost" size="xs"><Edit2 className="w-4 h-4" /></Button>
          </Link>
          <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)}>
            <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
          </Button>
        </div>
      ),
    },
  ]

  const isFiltering = search.trim().length > 0

  return (
    <>
      <PageHeader
        title="Organizations"
        description="Manage all organizations in the system"
        actions={
          permissions.create_org ? (
            <Link href="/admin/organizations/create">
              <CreateButton>Create Organization</CreateButton>
            </Link>
          ) : undefined
        }
      />

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search organizations..."
          className="max-w-[300px]"
        />

        {isFiltering && data && (
          <span className="text-[13px] text-[var(--text-3)]">
            <strong className="text-[var(--text-1)]">{data.total}</strong> result{data.total !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {error ? (
        <DataTable columns={columns} data={[]} error={error} onRetry={refetch} />
      ) : !loading && organizations.length === 0 ? (
        isFiltering ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <SlidersHorizontal className="w-10 h-10 text-[var(--text-3)] mb-3" />
            <p className="text-[15px] font-medium">No organizations match &ldquo;{search}&rdquo;</p>
            <Button variant="ghost" size="sm" className="mt-4" onClick={() => handleSearchChange('')}>
              Clear search
            </Button>
          </div>
        ) : (
          <EmptyState
            icon={Building2}
            title="No organizations yet"
            description="Create your first organization."
            action={
              permissions.create_org ? (
                <Link href="/admin/organizations/create">
                  <CreateButton>Create Organization</CreateButton>
                </Link>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          <DataTable
            columns={columns}
            data={organizations}
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
              onPageSizeChange={s => { setPageSize(s); setPage(1) }}
            />
          )}
        </>
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Delete Organization"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>Delete</Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-[14px] text-[var(--text-2)]">
            Delete <strong>{deleteTarget?.name}</strong>? This cannot be undone.
          </p>
          {deleteCounts && deleteCounts.users + deleteCounts.agents + deleteCounts.tools + deleteCounts.db > 0 && (
            <div className="rounded-[var(--radius-md)] border border-amber-300/50 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 px-3.5 py-3">
              <p className="text-[13px] font-medium text-amber-800 dark:text-amber-300">This will also remove:</p>
              <ul className="mt-1.5 text-[13px] text-amber-700 dark:text-amber-200/90 space-y-0.5 list-disc list-inside">
                {deleteCounts.users > 0 && <li>{deleteCounts.users} user{deleteCounts.users === 1 ? '' : 's'}</li>}
                {deleteCounts.agents > 0 && <li>{deleteCounts.agents} agent{deleteCounts.agents === 1 ? '' : 's'}</li>}
                {deleteCounts.tools > 0 && <li>{deleteCounts.tools} tool{deleteCounts.tools === 1 ? '' : 's'}</li>}
                {deleteCounts.db > 0 && <li>{deleteCounts.db} database connection{deleteCounts.db === 1 ? '' : 's'}</li>}
              </ul>
            </div>
          )}
        </div>
      </Dialog>

      <Dialog
        open={!!bulkDeleteTarget}
        onOpenChange={open => !open && setBulkDeleteTarget(null)}
        title="Delete Organizations"
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
          Delete the <strong>{bulkDeleteTarget?.ids.length}</strong> selected organization{bulkDeleteTarget?.ids.length === 1 ? '' : 's'}?
          This also removes every user, agent, tool, and database connection that belongs to them. This cannot be undone.
        </p>
      </Dialog>
    </>
  )
}
