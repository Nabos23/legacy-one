'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Edit2, Trash2, MessageSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { Badge } from '@/components/ui/badge'
import { DataTable, type Column } from '@/components/ui/data-table'
import { Pagination } from '@/components/ui/pagination'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { useAgents } from '@/hooks/use-agents'
import { agentsApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import { truncate, formatDate, stripMarkdown } from '@/lib/utils'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import type { AgentPublic } from '@/types'

export function AgentListCard({ basePath = '/client' }: { basePath?: string }) {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AgentPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const { data, loading, refetch } = useAgents(page)
  const { toast } = useToast()

  const agents = (data?.items ?? []).filter(a =>
    a.name.toLowerCase().includes(search.toLowerCase())
  )

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await agentsApi.delete(deleteTarget.id!)
      toast.success(`Deleted ${deleteTarget.name}`)
      setDeleteTarget(null)
      refetch()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setDeleting(false)
    }
  }

  const columns: Column<AgentPublic>[] = [
    {
      key: 'name',
      header: 'Name',
      render: row => (
        <div className="flex items-center gap-3">
          <AgentAvatar
            name={row.name}
            avatarType={row.avatar_type}
            avatarValue={row.avatar_value}
            avatarUrl={row.avatar_url}
            size="sm"
          />
          <Link href={`${basePath}/agents/${row.id}`} className="font-medium hover:text-violet-600 dark:hover:text-violet-400 transition-colors">
            {row.name}
          </Link>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: row => (
        <div className="flex items-center gap-2">
          <StatusIndicator status={row.is_active !== false ? 'active' : 'inactive'} pulse />
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
      key: 'created_at',
      header: 'Created',
      render: row => <span className="text-[13px]">{formatDate(row.created_at)}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: row => (
        <div className="flex items-center gap-1">
          <Link href={`${basePath}/playground?agent=${row.id}`}>
            <Button variant="ghost" size="xs"><MessageSquare className="w-4 h-4" /></Button>
          </Link>
          <Link href={`${basePath}/agents/${row.id}/edit`}>
            <Button variant="ghost" size="xs"><Edit2 className="w-4 h-4" /></Button>
          </Link>
          <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)}>
            <Trash2 className="w-4 h-4 text-red-600 dark:text-red-400" />
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="card-1 rounded-[var(--radius-lg)] overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <h3 className="text-[15px] font-bold text-[var(--text-1)]">Your Agents</h3>
          {data && <Badge variant="primary">{data.total} total</Badge>}
        </div>
        <div className="flex gap-3">
          <SearchInput
            placeholder="Search agents..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="max-w-[220px]"
          />
        </div>
      </div>

      <DataTable
        columns={columns}
        data={agents}
        isLoading={loading}
        emptyMessage="No agents yet"
        emptyDescription="Create your first agent to start automating."
        emptyAction={
          <Link href={`${basePath}/agents/create`}>
            <CreateButton size="sm">Create Agent</CreateButton>
          </Link>
        }
      />

      {data && data.total > data.page_size && (
        <Pagination page={page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
      )}

      {deleteTarget && (
        <div className="animate-fadeIn fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-[400px] p-6 rounded-2xl
            bg-white/95 dark:bg-[#111122]/96
            backdrop-blur-2xl
            border border-black/[0.08] dark:border-white/[0.1]
            shadow-[0_24px_60px_rgba(0,0,0,0.15)] dark:shadow-[0_24px_60px_rgba(0,0,0,0.7)]
            animate-scaleIn">
            <h3 className="text-[16px] font-semibold mb-2">Delete agent?</h3>
            <p className="text-[13px] text-[var(--text-3)] mb-5">
              "<span className="text-[var(--text-1)]">{deleteTarget.name}</span>" will be permanently deleted.
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setDeleteTarget(null)}>Cancel</Button>
              <Button variant="danger" size="sm" onClick={handleDelete} disabled={deleting}>
                {deleting ? 'Deleting…' : 'Delete'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
