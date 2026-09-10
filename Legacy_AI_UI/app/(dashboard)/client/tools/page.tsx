'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import {
  Wrench, Edit2, Trash2, X, SlidersHorizontal, Eye,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { PageHeader } from '@/components/ui/page-header'
import { DataTable, type Column } from '@/components/ui/data-table'
import { BulkDeleteButton } from '@/components/ui/bulk-delete-button'
import { EmptyState } from '@/components/ui/empty-state'
import { Pagination } from '@/components/ui/pagination'
import { Dialog } from '@/components/ui/dialog'
import { useTools } from '@/hooks/use-tools'
import { useBulkDelete } from '@/hooks/use-bulk-delete'
import { useToast } from '@/hooks/use-toast'
import { toolsApi } from '@/lib/api'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import { avatarColor, formatDate, formatToolName, truncate } from '@/lib/utils'
import { useAuth } from '@/contexts/auth-context'
import type { ToolPublic } from '@/types'

function getToolDisplayName(tool: ToolPublic) {
  const raw = tool.name || tool.user_description || tool.tool_id
  return formatToolName(raw)
}

export default function ToolsPage() {
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ToolPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<{ ids: string[]; clear: () => void } | null>(null)
  const [pageSize, setPageSize] = useState(10)
  const { data, loading, error, refetch, page, setPage } = useTools(1, undefined, pageSize)
  const { permissions } = useAuth()
  const { toast } = useToast()
  const bulkDelete = useBulkDelete(id => toolsApi.delete(id), { entity: 'tool', onDone: refetch })

  const tools = useMemo(() => {
    const items = data?.items ?? []
    if (!search.trim()) return items
    const q = search.toLowerCase()
    return items.filter(t =>
      getToolDisplayName(t).toLowerCase().includes(q) ||
      (t.name ?? '').toLowerCase().includes(q) ||
      (t.user_description || '').toLowerCase().includes(q) ||
      t.tool_id.toLowerCase().includes(q)
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
      await toolsApi.delete(deleteTarget.id!)
      toast.success(`Deleted ${getToolDisplayName(deleteTarget)}`)
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete tool')
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

  const columns: Column<ToolPublic>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      sortAccessor: row => getToolDisplayName(row),
      render: row => (
        <Link href={`/client/tools/${row.id}`} className="flex items-center gap-2 hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
          <Wrench className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          <span className="font-medium">{getToolDisplayName(row)}</span>
        </Link>
      ),
    },
    {
      key: 'user_description',
      header: 'Description',
      render: row => (
        <span className="text-[13px] text-[var(--text-3)]">{truncate(row.user_description || '', 70)}</span>
      ),
    },
    {
      key: 'agent_name',
      header: 'Agent',
      sortable: true,
      sortAccessor: row => row.agent_name ?? '',
      render: row => {
        const label = row.agent_name ?? row.tool_id.slice(-12)
        return (
          <div className="flex items-center gap-2">
            <AgentAvatar
              name={label}
              avatarType={row.agent_avatar_type}
              avatarValue={row.agent_avatar_value}
              avatarUrl={row.agent_avatar_url}
              size="xs"
            />
            <span className="text-[13px] text-[var(--text-2)] truncate max-w-[160px]">{label}</span>
          </div>
        )
      },
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
          <Link href={`/client/tools/${row.id}`}>
            <Button variant="ghost" size="xs">
              <Eye className="w-4 h-4" />
            </Button>
          </Link>
          {permissions.edit_tool && (
            <Link href={`/client/tools/${row.id}`}>
              <Button variant="ghost" size="xs">
                <Edit2 className="w-4 h-4" />
              </Button>
            </Link>
          )}
          {permissions.delete_tool && (
            <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)}>
              <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
            </Button>
          )}
        </div>
      ),
    },
  ]

  const totalLoaded = data?.items.length ?? 0
  const showingFiltered = search.trim() && tools.length !== totalLoaded

  return (
    <>
      <PageHeader
        title="Tools"
        description="Manage tools available to your agents"
        actions={
          permissions.create_tool ? (
            <Link href="/client/tools/create">
              <CreateButton>Create Tool</CreateButton>
            </Link>
          ) : undefined
        }
      />

      {/* Search bar */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search tools..."
          className="max-w-[280px]"
        />

        {showingFiltered && (
          <span className="text-[13px] text-[var(--text-3)]">
            Showing <strong className="text-[var(--text-1)]">{tools.length}</strong> of {totalLoaded}
          </span>
        )}
      </div>

      {error ? (
        <DataTable columns={columns} data={[]} error={error} onRetry={refetch} />
      ) : !loading && tools.length === 0 ? (
        search ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <SlidersHorizontal className="w-10 h-10 text-[var(--text-3)] mb-3" />
            <p className="text-[15px] font-medium">No tools match "{search}"</p>
            <p className="text-[13px] text-[var(--text-3)] mt-1">Try a different search term</p>
            <Button variant="ghost" size="sm" className="mt-4" onClick={() => handleSearchChange('')}>
              Clear search
            </Button>
          </div>
        ) : (
          <EmptyState
            icon={Wrench}
            title="No tools yet"
            description="Register your first tool from the registry"
            action={
              permissions.create_tool ? (
                <Link href="/client/tools/create">
                  <CreateButton>Create Tool</CreateButton>
                </Link>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          <DataTable
            columns={columns}
            data={tools}
            isLoading={loading}
            getRowId={row => row.id!}
            bulkActions={({ ids, clear }) => (
              <BulkDeleteButton count={ids.length} busy={bulkDelete.busy} onClick={() => setBulkDeleteTarget({ ids, clear })} />
            )}
          />
          {data && !search && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.total}
              onPageChange={setPage}
              pageSizeOptions={[5, 10, 20, 50]}
              onPageSizeChange={size => {
                setPageSize(size)
                setPage(1)
              }}
            />
          )}
        </>
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Delete Tool"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>Delete</Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Delete <strong>{deleteTarget ? getToolDisplayName(deleteTarget) : ''}</strong>?
        </p>
      </Dialog>

      <Dialog
        open={!!bulkDeleteTarget}
        onOpenChange={open => !open && setBulkDeleteTarget(null)}
        title="Delete Tools"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setBulkDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleBulkDelete} disabled={bulkDelete.busy}>Delete</Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Are you sure you want to delete the {bulkDeleteTarget?.ids.length} selected tool(s)? This cannot be undone.
        </p>
      </Dialog>
    </>
  )
}
