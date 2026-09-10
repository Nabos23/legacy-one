'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { MessageCircle, Trash2, ChevronRight, Users, Bot, Loader2, Power, Copy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { Select } from '@/components/ui/select'
import { StatsCard } from '@/components/ui/stats-card'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { PageHeader } from '@/components/ui/page-header'
import { Pagination } from '@/components/ui/pagination'
import { widgetsApi } from '@/lib/api/widgets'
import { useAuth } from '@/contexts/auth-context'
import { useOrganizations } from '@/hooks/use-organizations'
import { useToast } from '@/hooks/use-toast'
import type { WidgetConfigPublic } from '@/types'

interface WidgetsListViewProps {
  /** e.g. "/client/widgets" or "/admin/widgets" -- every link on this page is relative to it. */
  basePath: string
  /** Show the cross-org filter + an Organization column. Only meaningful for super admins. */
  showOrgFilter?: boolean
}

export function WidgetsListView({ basePath, showOrgFilter }: WidgetsListViewProps) {
  const router = useRouter()
  const { user, permissions } = useAuth()
  const { toast } = useToast()
  const [widgets, setWidgets] = useState<WidgetConfigPublic[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [loading, setLoading] = useState(true)
  const [orgFilter, setOrgFilter] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<WidgetConfigPublic | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null)

  const isSuperAdmin = !!permissions?.is_super_admin
  const { data: orgsData } = useOrganizations(1, undefined, 100)
  const orgNameMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const org of orgsData?.items ?? []) {
      if (org.id) map[org.id] = org.name
    }
    return map
  }, [orgsData?.items])

  const fetchWidgets = async () => {
    setLoading(true)
    try {
      const scopeOrgId = showOrgFilter && isSuperAdmin ? orgFilter || undefined : user?.organization_id
      const data = await widgetsApi.list(page, pageSize, scopeOrgId)
      setWidgets(data.items)
      setTotal(data.total)
    } catch {
      toast.error('Failed to load widgets')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchWidgets() }, [user?.organization_id, orgFilter, isSuperAdmin, page, pageSize])

  const handleOrgFilterChange = (val: string) => {
    setOrgFilter(val)
    setPage(1)
  }

  const handlePageSizeChange = (size: number) => {
    setPageSize(size)
    setPage(1)
  }

  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await widgetsApi.delete(deleteTarget.id!)
      setWidgets(prev => prev.filter(w => w.id !== deleteTarget.id))
      setTotal(prev => Math.max(0, prev - 1))
      toast.success('Widget deleted')
      setDeleteTarget(null)
    } catch {
      toast.error('Failed to delete widget')
    } finally {
      setDeleting(false)
    }
  }

  const handleDuplicate = async (widget: WidgetConfigPublic) => {
    setDuplicatingId(widget.id!)
    try {
      const copy = await widgetsApi.duplicate(widget.id!)
      toast.success(`Duplicated as "${copy.name}"`)
      router.push(`${basePath}/${copy.id}`)
    } catch {
      toast.error('Failed to duplicate widget')
      setDuplicatingId(null)
    }
  }

  const orgOptions = [
    { value: '', label: 'All organizations' },
    ...(orgsData?.items ?? []).map(o => ({ value: o.id!, label: o.name })),
  ]

  const enabledCount = widgets.filter(w => w.is_enabled).length
  const supervisorCount = widgets.filter(w => w.source_type === 'supervisor').length

  return (
    <>
      <PageHeader
        title="Chatbot Widgets"
        description="Embeddable chat widgets your agents power on external websites"
        actions={
          <CreateButton onClick={() => router.push(`${basePath}/create`)}>
            New Chatbot Widget
          </CreateButton>
        }
      />

      {!loading && widgets.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatsCard label="Total widgets" value={total} icon={MessageCircle} color="primary" />
          <StatsCard label="Enabled" value={enabledCount} icon={Power} color="success" />
          <StatsCard label="Multi-agent" value={supervisorCount} icon={Users} color="info" />
        </div>
      )}

      {showOrgFilter && isSuperAdmin && (
        <div className="flex items-center gap-3 mb-5">
          <Select value={orgFilter} onValueChange={handleOrgFilterChange} options={orgOptions} className="w-[220px]" />
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-20 rounded-[var(--radius-lg)] bg-[var(--surface-2)] animate-pulse border border-[var(--border)]" />
          ))}
        </div>
      ) : widgets.length === 0 ? (
        <EmptyState
          icon={MessageCircle}
          title="No chatbot widgets yet"
          description="Create a chatbot widget to embed a chat experience on your own website or internal systems."
          action={
            <CreateButton onClick={() => router.push(`${basePath}/create`)}>
              Create your first widget
            </CreateButton>
          }
        />
      ) : (
        <div className="space-y-3">
          {widgets.map(widget => (
            <div
              key={widget.id}
              onClick={() => router.push(`${basePath}/${widget.id}`)}
              className="group card-1 rounded-[var(--radius-lg)] p-4 flex items-center gap-4 cursor-pointer hover:shadow-md transition-shadow duration-[220ms]"
            >
              <div
                className="w-11 h-11 rounded-xl border flex items-center justify-center shrink-0"
                style={{
                  backgroundColor: `${widget.branding.theme_color}1a`,
                  borderColor: `${widget.branding.theme_color}33`,
                  color: widget.branding.theme_color,
                }}
              >
                <MessageCircle className="w-5 h-5" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="text-[15px] font-semibold text-[var(--text-1)] truncate">{widget.name}</p>
                  <StatusIndicator status={widget.is_enabled ? 'active' : 'inactive'} pulse={widget.is_enabled} />
                  <Badge variant="neutral" className="text-[10px] shrink-0 gap-1">
                    {widget.source_type === 'supervisor' ? <Users className="w-2.5 h-2.5" /> : <Bot className="w-2.5 h-2.5" />}
                    {widget.source_type === 'supervisor' ? 'Multi-agent (supervisor)' : 'Single agent'}
                  </Badge>
                  {showOrgFilter && (
                    <Badge variant="outline" className="text-[10px] shrink-0">
                      {orgNameMap[widget.organization_id] ?? widget.organization_id.slice(-8)}
                    </Badge>
                  )}
                </div>
                <p className="text-[11px] text-[var(--text-3)] mt-1">
                  {widget.security.allowed_origins.length} allowed origin{widget.security.allowed_origins.length === 1 ? '' : 's'}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={e => { e.stopPropagation(); handleDuplicate(widget) }}
                  disabled={duplicatingId === widget.id}
                  className="opacity-0 group-hover:opacity-100"
                  title="Duplicate widget"
                >
                  {duplicatingId === widget.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Copy className="w-4 h-4" />}
                </Button>
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={e => { e.stopPropagation(); setDeleteTarget(widget) }}
                  className="opacity-0 group-hover:opacity-100"
                  title="Delete widget"
                >
                  <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
                </Button>
                <ChevronRight className="w-4 h-4 text-[var(--text-3)] group-hover:text-violet-500 transition-colors" />
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && total > pageSize && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
          pageSizeOptions={[5, 10, 20, 50]}
        />
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Delete widget"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDeleteConfirmed} disabled={deleting}>
              {deleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Delete
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Delete <strong>{deleteTarget?.name}</strong>? Its embed script will stop working immediately. This cannot be undone.
        </p>
      </Dialog>
    </>
  )
}
