'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { GitBranch, Trash2, MessageSquare, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { Badge } from '@/components/ui/badge'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Pagination } from '@/components/ui/pagination'
import { orchestrationsApi } from '@/lib/api/orchestrations'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/contexts/auth-context'
import type { OrchestrationPublic } from '@/types'

export default function OrchestrationsPage() {
  const router = useRouter()
  const { toast } = useToast()
  const { permissions } = useAuth()
  const [orchestrations, setOrchestrations] = useState<OrchestrationPublic[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [loading, setLoading] = useState(true)
  const [deleteTarget, setDeleteTarget] = useState<OrchestrationPublic | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchOrchestrations = async () => {
    try {
      const data = await orchestrationsApi.list(page, pageSize)
      setOrchestrations(data.items)
      setTotal(data.total)
    } catch {
      toast.error('Failed to load orchestrations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchOrchestrations() }, [page, pageSize])

  const handlePageSizeChange = (size: number) => {
    setPageSize(size)
    setPage(1)
  }

  const handleDeleteConfirmed = async () => {
    const orch = deleteTarget
    if (!orch?.id) return
    setDeleting(true)
    try {
      await orchestrationsApi.delete(orch.id)
      setOrchestrations(prev => prev.filter(o => o.id !== orch.id))
      setTotal(prev => Math.max(0, prev - 1))
      toast.success('Orchestration deleted')
      setDeleteTarget(null)
    } catch {
      toast.error('Failed to delete orchestration')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="flex flex-col min-h-0 flex-1 p-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-[22px] font-bold text-[var(--text-1)] tracking-tight">Orchestrations</h1>
          <p className="text-[13px] text-[var(--text-3)] mt-1">Build multi-agent workflows with directed connections</p>
        </div>
        {permissions.create_agent && (
          <CreateButton onClick={() => router.push('/client/orchestrations/create')}>
            New Orchestration
          </CreateButton>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-2xl bg-[var(--surface-2)] animate-pulse border border-[var(--border)]" />
          ))}
        </div>
      ) : orchestrations.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center py-24 text-[var(--text-2)]">
          <div className="w-16 h-16 rounded-2xl bg-violet-50 dark:bg-violet-500/10 border border-violet-100 dark:border-violet-500/20 flex items-center justify-center text-violet-500 mb-4">
            <GitBranch className="w-8 h-8" />
          </div>
          <p className="text-[16px] font-bold text-[var(--text-1)] mb-2">No orchestrations yet</p>
          <p className="text-[13px] text-[var(--text-3)] mb-6 text-center max-w-xs">
            Create a multi-agent orchestration to route tasks across specialist agents in a defined flow.
          </p>
          <CreateButton onClick={() => router.push('/client/orchestrations/create')}>
            Create your first orchestration
          </CreateButton>
        </div>
      ) : (
        <div className="space-y-3">
          {orchestrations.map(orch => (
            <div
              key={orch.id}
              onClick={() => router.push(`/client/orchestrations/${orch.id}`)}
              className="group flex items-center gap-4 p-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)] hover:border-violet-200 dark:hover:border-violet-500/30 hover:shadow-md transition-[border-color,box-shadow] cursor-pointer"
            >
              <div className="w-11 h-11 rounded-xl bg-violet-50 dark:bg-violet-500/10 border border-violet-100 dark:border-violet-500/20 flex items-center justify-center text-violet-600 shrink-0">
                <GitBranch className="w-5 h-5" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-[15px] font-semibold text-[var(--text-1)] truncate">{orch.name}</p>
                  <Badge variant="neutral" className="text-[10px] shrink-0">
                    {orch.agents.length} agents
                  </Badge>
                  <Badge variant="neutral" className="text-[10px] shrink-0">
                    {orch.connections.length} connections
                  </Badge>
                </div>
                {orch.description && (
                  <p className="text-[12px] text-[var(--text-3)] truncate">{orch.description}</p>
                )}
                <p className="text-[11px] text-[var(--text-3)] mt-1">
                  Depth limit: {orch.max_depth} · Timeout: {orch.timeout_sec}s
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={e => { e.stopPropagation(); router.push(`/client/orchestrations/${orch.id}/chat`) }}
                  className="rounded-lg text-[12px] gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <MessageSquare className="w-3.5 h-3.5" /> Chat
                </Button>
                {permissions.delete_agent && (
                  <button
                    onClick={e => { e.stopPropagation(); setDeleteTarget(orch) }}
                    className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 text-[var(--text-3)] hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
                <ChevronRight className="w-4 h-4 text-[var(--text-3)] group-hover:text-violet-500 transition-colors" />
              </div>
            </div>
          ))}
        </div>
      )}

      {total > pageSize && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
          pageSizeOptions={[5, 10, 20, 50]}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={open => { if (!open) setDeleteTarget(null) }}
        title="Delete orchestration?"
        description={
          <>
            Delete <span className="font-medium text-[var(--text-1)]">{deleteTarget?.name}</span>?
            This removes the workflow and its agent connections — chat history stays intact.
          </>
        }
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={handleDeleteConfirmed}
      />
    </div>
  )
}
