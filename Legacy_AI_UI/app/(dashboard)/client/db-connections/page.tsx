'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Database, Eye, EyeOff, Trash2, Edit2, SlidersHorizontal, LayoutList } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { PageHeader } from '@/components/ui/page-header'
import { DataTable, type Column } from '@/components/ui/data-table'
import { BulkDeleteButton } from '@/components/ui/bulk-delete-button'
import { EmptyState } from '@/components/ui/empty-state'
import { Pagination } from '@/components/ui/pagination'
import { Dialog } from '@/components/ui/dialog'
import { useDbConnections } from '@/hooks/use-db-connections'
import { useBulkDelete } from '@/hooks/use-bulk-delete'
import { useToast } from '@/hooks/use-toast'
import { dbConnectionsApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { useAuth } from '@/contexts/auth-context'
import type { DbConnectionPublic } from '@/types'

function maskConnection(str: string) {
  if (str.length <= 20) return `${str.slice(0, 8)}***`
  return `${str.slice(0, 20)}***@...`
}

function formatConnectionType(type?: string) {
  if (!type) return 'Database'
  const labels: Record<string, string> = {
    postgresql: 'PostgreSQL',
    postgres: 'PostgreSQL',
    mysql: 'MySQL',
    mariadb: 'MariaDB',
    sqlite: 'SQLite',
    mssql: 'SQL Server',
    mongodb: 'MongoDB',
    firebase: 'Firebase',
    other: 'Other',
  }
  return labels[type.toLowerCase()] ?? type
}

export default function DbConnectionsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [revealed, setRevealed] = useState<Record<string, boolean>>({})
  const [deleteTarget, setDeleteTarget] = useState<DbConnectionPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<{ ids: string[]; clear: () => void } | null>(null)
  const { data, loading, error, refetch } = useDbConnections(page)
  const { permissions } = useAuth()
  const { toast } = useToast()
  const bulkDelete = useBulkDelete(id => dbConnectionsApi.delete(id), { entity: 'connection', onDone: refetch })

  const connections = useMemo(() => {
    const items = data?.items ?? []
    if (!search.trim()) return items
    const q = search.toLowerCase()
    return items.filter(c =>
      (c.id || '').toLowerCase().includes(q) ||
      (c.name || '').toLowerCase().includes(q) ||
      (c.connection_type || '').toLowerCase().includes(q) ||
      c.connection_string.toLowerCase().includes(q) ||
      (c.organization_id || '').toLowerCase().includes(q)
    )
  }, [data?.items, search])

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await dbConnectionsApi.delete(deleteTarget.id!)
      toast.success('Connection removed')
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete connection')
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

  const columns: Column<DbConnectionPublic>[] = [
    {
      key: 'connection_string',
      header: 'Connection',
      render: row => (
        <div className="flex items-start gap-2 min-w-0">
          <Database className="w-4 h-4 text-violet-600 dark:text-violet-400 shrink-0" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-medium text-[var(--text-1)]">
                {row.name || 'Unnamed connection'}
              </span>
              <span className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 text-[11px] text-[var(--text-2)]">
                {formatConnectionType(row.connection_type)}
              </span>
            </div>
            <div
              className="mt-1 truncate font-mono text-[12px] text-[var(--text-3)]"
              title={revealed[row.id!] ? row.connection_string : undefined}
            >
              {revealed[row.id!] ? row.connection_string : maskConnection(row.connection_string)}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      sortAccessor: row => row.created_at ?? '',
      render: row => <span className="text-[12px] text-[var(--text-3)]">{formatDate(row.created_at)}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: row => (
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="xs"
            onClick={() => setRevealed(prev => ({ ...prev, [row.id!]: !prev[row.id!] }))}
            title={revealed[row.id!] ? 'Hide' : 'Reveal'}
          >
            {revealed[row.id!] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </Button>
          <Link href={`/client/db-connections/${row.id!}/schema`} title="View schema">
            <Button variant="ghost" size="xs">
              <LayoutList className="w-4 h-4" />
            </Button>
          </Link>
          {permissions.edit_db_connection && (
            <Link href={`/client/db-connections/${row.id!}/edit`} title="Edit">
              <Button variant="ghost" size="xs">
                <Edit2 className="w-4 h-4" />
              </Button>
            </Link>
          )}
          {permissions.delete_db_connection && (
            <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)} title="Delete">
              <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
            </Button>
          )}
        </div>
      ),
    },
  ]

  const totalLoaded = data?.items.length ?? 0
  const showingFiltered = search.trim() && connections.length !== totalLoaded

  return (
    <>
      <PageHeader
        title="DB Connections"
        description="Manage database connections for your tools"
        actions={
          permissions.create_db_connection ? (
            <Link href="/client/db-connections/create">
              <CreateButton>Add Connection</CreateButton>
            </Link>
          ) : undefined
        }
      />

      {/* Search bar */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search by name, ID, or type..."
          className="max-w-[300px]"
        />
        {showingFiltered && (
          <span className="text-[13px] text-[var(--text-3)]">
            Showing <strong className="text-[var(--text-1)]">{connections.length}</strong> of {totalLoaded}
          </span>
        )}
      </div>

      {error ? (
        <DataTable columns={columns} data={[]} error={error} onRetry={refetch} />
      ) : !loading && connections.length === 0 ? (
        search ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <SlidersHorizontal className="w-10 h-10 text-[var(--text-3)] mb-3" />
            <p className="text-[15px] font-medium">No connections match "{search}"</p>
            <Button variant="ghost" size="sm" className="mt-4" onClick={() => handleSearchChange('')}>
              Clear search
            </Button>
          </div>
        ) : (
          <EmptyState
            icon={Database}
            title="No connections yet"
            description="Add a database connection for your tools"
            action={
              permissions.create_db_connection ? (
                <Link href="/client/db-connections/create">
                  <CreateButton>Add Connection</CreateButton>
                </Link>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          <DataTable
            columns={columns}
            data={connections}
            isLoading={loading}
            getRowId={row => row.id!}
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
          {data && !search && (
            <Pagination
              page={page}
              pageSize={data.page_size}
              total={data.total}
              onPageChange={setPage}
            />
          )}
        </>
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Remove Connection"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>Delete</Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Removing this connection may break tools that depend on it. Continue?
        </p>
      </Dialog>

      <Dialog
        open={!!bulkDeleteTarget}
        onOpenChange={open => !open && setBulkDeleteTarget(null)}
        title="Remove Connections"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setBulkDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleBulkDelete} disabled={bulkDelete.busy}>Delete</Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Are you sure you want to remove the {bulkDeleteTarget?.ids.length} selected connection(s)? Removing connections may break tools that depend on them. Continue?
        </p>
      </Dialog>
    </>
  )
}
