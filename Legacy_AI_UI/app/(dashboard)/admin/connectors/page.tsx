'use client'

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import Link from 'next/link'
import {
  PlugZap, Eye, EyeOff, ShieldOff, Link2, LayoutList, LayoutGrid,
  Loader2, CheckCircle2, XCircle, ToggleLeft, ToggleRight,
  Key, Cpu, Users, X, RefreshCw, Info, ListChecks,
  ArrowRight, MessageCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/search-input'
import { Dialog } from '@/components/ui/dialog'
import { PageHeader } from '@/components/ui/page-header'
import { Pagination } from '@/components/ui/pagination'
import { DataTable, type Column, type SortState } from '@/components/ui/data-table'
import { Tabs } from '@/components/ui/tabs'
import { ConnectorLogo } from '@/components/connectors/connector-logo'
import { ConnectorSetupDialog } from '@/components/connectors/connector-setup-dialog'
import { humanizeAction } from '@/components/connectors/connector-card'
import { connectorsApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useToast } from '@/hooks/use-toast'
import { useConnectorStatuses } from '@/hooks/use-connector-statuses'
import { cn } from '@/lib/utils'
import type { ConnectorRegistryItem, ConnectorRegistryPage } from '@/types/connectors'

type Tab = 'catalog' | 'connections'
type ViewMode = 'table' | 'grid'

const AUTH_TYPE_LABELS: Record<string, string> = {
  oauth2: 'OAuth 2.0',
  bot_token: 'Bot Token',
  api_key: 'API Key',
  basic: 'Basic Auth',
}

const SCOPE_LABELS: Record<string, string> = {
  organization: 'Org',
  user: 'User',
}

const PAGE_SIZE_OPTIONS = [10, 25, 50]

const CATALOG_COLUMNS = (
  togglingId: string | null,
  onToggleVisibility: (row: ConnectorRegistryItem) => void,
  onViewActions: (row: ConnectorRegistryItem) => void,
): Column<ConnectorRegistryItem>[] => [
  {
    key: 'name',
    header: 'Connector',
    sortable: true,
    render: row => (
      <div className="flex items-center gap-3">
        <ConnectorLogo providerId={row.provider_id} size="sm" />
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-[var(--text-1)]">{row.name}</span>
            {!row.is_visible && <Badge variant="neutral" className="text-[10px]">hidden</Badge>}
            {row.available_actions.length > 0 && (
              <button
                type="button"
                onClick={() => onViewActions(row)}
                aria-label={`View ${row.available_actions.length} available actions`}
                title={`${row.available_actions.length} available action${row.available_actions.length === 1 ? '' : 's'}`}
                className="flex items-center gap-1 h-4 shrink-0 px-1.5 rounded-full text-[9.5px] font-medium text-[var(--text-3)] hover:text-[var(--text-1)] bg-black/[0.03] dark:bg-white/[0.04] hover:bg-black/[0.05] dark:hover:bg-white/[0.08] transition-colors"
              >
                <Info className="w-3 h-3 shrink-0" />
                {row.available_actions.length}
              </button>
            )}
          </div>
          <p className="text-[11px] text-[var(--text-3)] max-w-[220px] truncate mt-0.5">{row.description}</p>
        </div>
      </div>
    ),
  },
  {
    key: 'category',
    header: 'Category',
    sortable: true,
    render: row => <span className="text-[12px] text-[var(--text-2)]">{row.category}</span>,
  },
  {
    key: 'auth_type',
    header: 'Auth type',
    render: row => (
      <div className="flex items-center gap-1.5">
        <Key className="w-3 h-3 text-[var(--text-3)]" />
        <span className="text-[12px] text-[var(--text-2)]">
          {AUTH_TYPE_LABELS[row.auth_type] ?? row.auth_type}
        </span>
      </div>
    ),
  },
  {
    key: 'owner_scope',
    header: 'Scope',
    render: row => (
      <div className="flex items-center gap-1.5">
        {row.owner_scope === 'organization'
          ? <Cpu className="w-3 h-3 text-[var(--text-3)]" />
          : <Users className="w-3 h-3 text-[var(--text-3)]" />
        }
        <span className="text-[12px] text-[var(--text-2)]">
          {SCOPE_LABELS[row.owner_scope] ?? row.owner_scope}
        </span>
      </div>
    ),
  },
  {
    key: 'is_visible',
    header: 'Visibility',
    render: row => (
      <button
        type="button"
        onClick={() => onToggleVisibility(row)}
        disabled={togglingId === row.id}
        className="flex items-center gap-2 group/toggle disabled:opacity-50"
      >
        {togglingId === row.id ? (
          <Loader2 className="w-5 h-5 animate-spin text-[var(--text-3)]" />
        ) : row.is_visible ? (
          <ToggleRight className="w-[22px] h-[22px] text-violet-500 group-hover/toggle:scale-110 transition-transform" />
        ) : (
          <ToggleLeft className="w-[22px] h-[22px] text-[var(--text-3)] group-hover/toggle:scale-110 transition-transform" />
        )}
        <span className={cn(
          'text-[12px] font-medium',
          row.is_visible ? 'text-violet-600 dark:text-violet-400' : 'text-[var(--text-3)]'
        )}>
          {row.is_visible ? 'Visible' : 'Hidden'}
        </span>
      </button>
    ),
  },
]

export default function AdminConnectorsPage() {
  const { permissions } = useAuth()
  const { toast } = useToast()

  const [tab, setTab] = useState<Tab>('catalog')
  const [viewMode, setViewMode] = useState<ViewMode>('table')

  // ── Catalog state ──────────────────────────────────────────────────────────
  const [catalogPage, setCatalogPage] = useState<ConnectorRegistryPage | null>(null)
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [sort, setSort] = useState<SortState>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Connections state ──────────────────────────────────────────────────────
  const [allConnectors, setAllConnectors] = useState<ConnectorRegistryItem[]>([])
  const [connectionsLoading, setConnectionsLoading] = useState(false)
  const [connectionsLoaded, setConnectionsLoaded] = useState(false)
  const connectorIds = useMemo(() => allConnectors.map(c => c.id), [allConnectors])
  const { statuses, loading: statusesLoading, setStatus, retryOne } = useConnectorStatuses(connectorIds)
  const [connectTarget, setConnectTarget] = useState<ConnectorRegistryItem | null>(null)
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null)
  const [retryingId, setRetryingId] = useState<string | null>(null)
  const [actionsConnector, setActionsConnector] = useState<ConnectorRegistryItem | null>(null)

  // ── Catalog: fetch when page/pageSize/search/category/sort changes ─────────
  const loadCatalog = useCallback(async (
    p: number, ps: number, q: string, cat: string, sortState: SortState
  ) => {
    setCatalogLoading(true)
    try {
      const data = await connectorsApi.getRegistryAdmin({
        page: p, page_size: ps, q: q || undefined, category: cat || undefined,
        sortBy: (sortState?.key as 'name' | 'category') ?? undefined,
        sortOrder: sortState?.dir,
      })
      setCatalogPage(data)
    } catch {
      toast.error('Failed to load connector registry')
    } finally {
      setCatalogLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (tab === 'catalog') {
      loadCatalog(page, pageSize, search, categoryFilter, sort)
    }
  }, [tab, page, pageSize, search, categoryFilter, sort, loadCatalog])

  // Debounce search input
  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (searchDebounce.current) clearTimeout(searchDebounce.current)
    searchDebounce.current = setTimeout(() => {
      setPage(1)
      setSearch(val)
    }, 350)
  }

  const clearSearch = () => {
    setSearchInput('')
    setSearch('')
    setPage(1)
  }

  // ── Connections: load all once when tab is first opened ────────────────────
  // Status checks for the loaded ids are kicked off automatically by
  // useConnectorStatuses (via the connectorIds dependency above).
  const loadConnections = useCallback(async () => {
    setConnectionsLoading(true)
    try {
      const data = await connectorsApi.getRegistryAdmin({ page: 1, page_size: 200 })
      setAllConnectors(data.items)
      setConnectionsLoaded(true)
    } catch {
      toast.error('Failed to load connectors')
    } finally {
      setConnectionsLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (tab === 'connections' && !connectionsLoaded) {
      loadConnections()
    }
  }, [tab, connectionsLoaded, loadConnections])

  // ── Catalog actions ────────────────────────────────────────────────────────
  const handleToggleVisibility = async (connector: ConnectorRegistryItem) => {
    setTogglingId(connector.id)
    const next = !connector.is_visible
    // Optimistic update in current page
    setCatalogPage(prev => prev
      ? { ...prev, items: prev.items.map(c => c.id === connector.id ? { ...c, is_visible: next } : c) }
      : prev
    )
    try {
      await connectorsApi.setVisibility(connector.id, next)
      toast.success(next ? `${connector.name} is now visible` : `${connector.name} hidden from catalog`)
    } catch {
      setCatalogPage(prev => prev
        ? { ...prev, items: prev.items.map(c => c.id === connector.id ? { ...c, is_visible: !next } : c) }
        : prev
      )
      toast.error('Failed to update visibility')
    } finally {
      setTogglingId(null)
    }
  }

  const handleBulkVisibility = async (ids: string[], visible: boolean, clear: () => void) => {
    setBulkBusy(true)
    try {
      const results = await Promise.allSettled(ids.map(id => connectorsApi.setVisibility(id, visible)))
      const ok = results.filter(r => r.status === 'fulfilled').length
      const failed = results.length - ok
      if (ok) {
        setCatalogPage(prev => prev
          ? { ...prev, items: prev.items.map(c => ids.includes(c.id) ? { ...c, is_visible: visible } : c) }
          : prev
        )
        toast.success(`${visible ? 'Shown' : 'Hidden'} ${ok} connector${ok === 1 ? '' : 's'}`)
      }
      if (failed) toast.error(`Failed to update ${failed} connector${failed === 1 ? '' : 's'}`)
      clear()
    } finally {
      setBulkBusy(false)
    }
  }

  // ── Connections actions ────────────────────────────────────────────────────
  const handleDisconnect = async (connector: ConnectorRegistryItem) => {
    setDisconnectingId(connector.id)
    try {
      await connectorsApi.disconnect(connector.id)
      setStatus(connector.id, { connected: false })
      toast.success(`Disconnected ${connector.name}`)
    } catch {
      toast.error(`Failed to disconnect ${connector.name}`)
    } finally {
      setDisconnectingId(null)
    }
  }

  const handleConnected = () => {
    if (!connectTarget) return
    setStatus(connectTarget.id, { connected: true })
    setConnectTarget(null)
  }

  const handleRetryStatus = async (connectorId: string) => {
    setRetryingId(connectorId)
    try {
      await retryOne(connectorId)
    } finally {
      setRetryingId(null)
    }
  }

  // ── Derived ────────────────────────────────────────────────────────────────
  const totalConnected = Object.values(statuses).filter(s => s?.connected).length

  // Categories from all loaded connectors (for connections tab category headers)
  const groupedForConnections = useMemo(() => {
    const groups: Record<string, ConnectorRegistryItem[]> = {}
    allConnectors.forEach(c => {
      if (!groups[c.category]) groups[c.category] = []
      groups[c.category].push(c)
    })
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [allConnectors])

  // ── Guard ──────────────────────────────────────────────────────────────────
  if (!permissions.is_super_admin) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center">
        <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center mb-4">
          <ShieldOff className="w-6 h-6 text-red-500" />
        </div>
        <p className="text-[15px] font-semibold text-[var(--text-1)]">Super admin access required</p>
        <p className="text-[13px] text-[var(--text-3)] mt-1.5">Only super admins can manage connectors.</p>
      </div>
    )
  }

  const catalogItems = catalogPage?.items ?? []
  const catalogTotal = catalogPage?.total ?? 0

  return (
    <>
      <PageHeader
        title="Connectors"
        description="Control the catalog and manage your own service connections."
      />

      {/* Distinct from the outbound "Slack" connector in the catalog below
          (agent calls Slack's API) -- this is our own Slack App, chatted
          with inbound. See app/(dashboard)/client/connectors/page.tsx for
          the matching client-side banner. */}
      <Link
        href="/admin/connectors/slack-app"
        className="mb-7 flex items-center gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3 hover:border-violet-300 transition-colors group"
      >
        <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-violet-500/10 shrink-0">
          <MessageCircle className="w-4.5 h-4.5 text-violet-600 dark:text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-[var(--text-1)]">Slack App — chat with an agent from Slack</p>
          <p className="text-[12px] text-[var(--text-3)]">Manage connected Slack workspaces and which agent answers each one, across every org.</p>
        </div>
        <ArrowRight className="w-4 h-4 text-[var(--text-3)] group-hover:text-violet-500 transition-colors shrink-0" />
      </Link>

      {/* ── Tab switcher ── */}
      <Tabs
        className="mb-7"
        value={tab}
        onChange={v => setTab(v as Tab)}
        tabs={[
          {
            value: 'catalog',
            label: (
              <span className="flex items-center gap-2">
                <LayoutList className="w-[15px] h-[15px]" />
                Catalog
              </span>
            ),
          },
          {
            value: 'connections',
            label: (
              <span className="flex items-center gap-2">
                <Link2 className="w-[15px] h-[15px]" />
                My Connections
                {totalConnected > 0 && (
                  <span className="px-[7px] py-px bg-violet-600 text-white text-[10px] font-bold rounded-full leading-[1.6]">
                    {totalConnected}
                  </span>
                )}
              </span>
            ),
          },
        ]}
      />

      {/* ══════════════════════════ CATALOG TAB ══════════════════════════════ */}
      {tab === 'catalog' && (
        <>
          {/* Search + stats row */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            {/* Search */}
            <div className="flex-1 min-w-[200px] max-w-xs">
              <SearchInput
                value={searchInput}
                onChange={e => handleSearchChange(e.target.value)}
                placeholder="Search connectors…"
                rightElement={searchInput ? (
                  <button
                    type="button"
                    onClick={clearSearch}
                    className="text-[var(--text-3)] hover:text-[var(--text-2)]"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                ) : undefined}
              />
            </div>

            {/* View toggle */}
            <div className="flex items-center gap-0.5 p-[3px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg">
              {([
                { mode: 'table' as ViewMode, icon: LayoutList },
                { mode: 'grid'  as ViewMode, icon: LayoutGrid  },
              ]).map(({ mode, icon: Icon }) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={cn(
                    'p-1.5 rounded-md transition-[background-color,color] duration-100',
                    viewMode === mode
                      ? 'bg-white dark:bg-white/10 shadow-sm text-[var(--text-1)]'
                      : 'text-[var(--text-3)] hover:text-[var(--text-2)]',
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                </button>
              ))}
            </div>

            {/* Stats */}
            <div className="flex items-center gap-2 ml-auto">
              {[
                { icon: PlugZap, value: catalogTotal, label: 'total', color: 'text-[var(--text-2)]' },
                { icon: Eye, value: catalogPage?.items.filter(c => c.is_visible).length ?? 0, label: 'visible on page', color: 'text-violet-600 dark:text-violet-400' },
              ].map(({ icon: Icon, value, label, color }) => (
                <div key={label} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">
                  <Icon className={cn('w-3.5 h-3.5', color)} />
                  <span className="text-[13px] font-semibold text-[var(--text-1)] tabular-nums">{value}</span>
                  <span className="text-[11px] text-[var(--text-3)]">{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Category filter chips */}
          {!search && (
            <div className="flex flex-wrap gap-1.5 mb-4">
              {['All', 'Storage', 'Email', 'Messaging', 'Productivity', 'CRM', 'Support',
                'Developer Tools', 'Payments', 'Communication', 'Project Management', 'Finance', 'Documents',
                'ITSM', 'Analytics', 'Design', 'E-Commerce', 'Knowledge Base', 'Freelance', 'Health',
                'Video', 'Marketing', 'Social Media', 'HR', 'Monitoring',
              ].map(cat => (
                <button
                  key={cat}
                  onClick={() => { setCategoryFilter(cat === 'All' ? '' : cat); setPage(1) }}
                  className={cn(
                    'px-2.5 py-1 rounded-md text-[11px] font-medium transition-[background-color,color] duration-100',
                    (cat === 'All' ? !categoryFilter : categoryFilter === cat)
                      ? 'bg-violet-600 text-white'
                      : 'bg-[var(--surface-2)] text-[var(--text-3)] border border-[var(--border)] hover:text-[var(--text-2)] hover:border-[var(--border-2)]'
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}

          {/* Catalog content */}
          <div key={viewMode} className="animate-fadeIn">
          {viewMode === 'table' ? (
            /* ── Table view — reuses DataTable for built-in skeleton/empty/error + bulk select ── */
            <DataTable<ConnectorRegistryItem>
              columns={CATALOG_COLUMNS(togglingId, handleToggleVisibility, setActionsConnector)}
              data={catalogItems}
              isLoading={catalogLoading}
              getRowId={row => row.id}
              sortState={sort}
              onSortChange={next => { setSort(next); setPage(1) }}
              bulkActions={({ ids, clear }) => (
                <>
                  <Button size="xs" variant="outline" disabled={bulkBusy} onClick={() => handleBulkVisibility(ids, true, clear)}>
                    <Eye className="w-3 h-3 mr-1.5" /> Show
                  </Button>
                  <Button size="xs" variant="outline" disabled={bulkBusy} onClick={() => handleBulkVisibility(ids, false, clear)}>
                    <EyeOff className="w-3 h-3 mr-1.5" /> Hide
                  </Button>
                </>
              )}
              emptyIcon={PlugZap}
              emptyMessage="No connectors found"
              emptyAction={(search || categoryFilter) ? (
                <button
                  onClick={() => { clearSearch(); setCategoryFilter(''); setPage(1) }}
                  className="text-[12px] text-violet-500 hover:underline"
                >
                  Clear filters
                </button>
              ) : undefined}
              pagination={{
                page, pageSize, total: catalogTotal,
                onPageChange: p => setPage(p),
                onPageSizeChange: ps => { setPageSize(ps); setPage(1) },
                pageSizeOptions: PAGE_SIZE_OPTIONS,
              }}
            />
          ) : catalogLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-6 h-6 animate-spin text-violet-500" />
            </div>
          ) : catalogItems.length === 0 ? (
            <div className="glass flex flex-col items-center justify-center py-16 text-center gap-2">
              <PlugZap className="w-8 h-8 text-[var(--text-3)]" />
              <p className="text-[13px] text-[var(--text-2)] font-medium">No connectors found</p>
              {(search || categoryFilter) && (
                <button
                  onClick={() => { clearSearch(); setCategoryFilter(''); setPage(1) }}
                  className="text-[12px] text-violet-500 hover:underline"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            /* ── Card grid view ── */
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {catalogItems.map(row => (
                  <div
                    key={row.id}
                    className={cn(
                      'glass group relative flex flex-col gap-3 p-4 rounded-[var(--radius-lg)]',
                      'transition-[box-shadow,transform] duration-200 hover:shadow-md hover:-translate-y-0.5',
                      !row.is_visible && 'opacity-60',
                    )}
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-2">
                      <ConnectorLogo providerId={row.provider_id} size="md" />
                      {/* Visibility toggle pill */}
                      <button
                        type="button"
                        onClick={() => handleToggleVisibility(row)}
                        disabled={togglingId === row.id}
                        className={cn(
                          'shrink-0 flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border transition-[background-color,border-color,color] duration-150 disabled:opacity-50',
                          row.is_visible
                            ? 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20 hover:bg-violet-500/20'
                            : 'bg-[var(--surface-2)] text-[var(--text-3)] border-[var(--border)] hover:border-[var(--border-2)]',
                        )}
                      >
                        {togglingId === row.id ? (
                          <Loader2 className="w-2.5 h-2.5 animate-spin" />
                        ) : row.is_visible ? (
                          <Eye className="w-2.5 h-2.5" />
                        ) : (
                          <EyeOff className="w-2.5 h-2.5" />
                        )}
                        {row.is_visible ? 'Visible' : 'Hidden'}
                      </button>
                    </div>

                    {/* Name + description */}
                    <div className="flex-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <p className="text-[13px] font-semibold text-[var(--text-1)] leading-tight">{row.name}</p>
                        {row.available_actions.length > 0 && (
                          <button
                            type="button"
                            onClick={() => setActionsConnector(row)}
                            aria-label={`View ${row.available_actions.length} available actions`}
                            title={`${row.available_actions.length} available action${row.available_actions.length === 1 ? '' : 's'}`}
                            className="flex items-center gap-1 h-4 px-1.5 rounded-full text-[9.5px] font-medium text-[var(--text-3)] hover:text-[var(--text-1)] bg-black/[0.03] dark:bg-white/[0.04] hover:bg-black/[0.05] dark:hover:bg-white/[0.08] transition-colors"
                          >
                            <Info className="w-3 h-3 shrink-0" />
                            {row.available_actions.length}
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-[var(--text-3)] mt-1 line-clamp-2 leading-relaxed">{row.description}</p>
                    </div>

                    {/* Footer meta */}
                    <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-[var(--border)]">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[var(--surface-2)] text-[var(--text-3)] border border-[var(--border)]">
                        {row.category}
                      </span>
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-[var(--surface-2)] text-[var(--text-3)] border border-[var(--border)]">
                        <Key className="w-2.5 h-2.5" />
                        {AUTH_TYPE_LABELS[row.auth_type] ?? row.auth_type}
                      </span>
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-[var(--surface-2)] text-[var(--text-3)] border border-[var(--border)]">
                        {row.owner_scope === 'organization'
                          ? <Cpu className="w-2.5 h-2.5" />
                          : <Users className="w-2.5 h-2.5" />
                        }
                        {SCOPE_LABELS[row.owner_scope] ?? row.owner_scope}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4">
                <Pagination
                  page={page}
                  pageSize={pageSize}
                  total={catalogTotal}
                  onPageChange={p => { setPage(p); }}
                  onPageSizeChange={ps => { setPageSize(ps); setPage(1); }}
                  pageSizeOptions={PAGE_SIZE_OPTIONS}
                />
              </div>
            </>
          )}
          </div>
        </>
      )}

      {/* ═══════════════════════ MY CONNECTIONS TAB ══════════════════════════ */}
      {tab === 'connections' && (
        <div>
          {/* Stats strip */}
          <div className="flex items-center gap-2 mb-6">
            {[
              { icon: PlugZap, value: allConnectors.length, label: 'available', color: 'text-[var(--text-2)]' },
              { icon: CheckCircle2, value: totalConnected, label: 'connected', color: 'text-green-500' },
              { icon: XCircle, value: allConnectors.length - totalConnected, label: 'not connected', color: 'text-[var(--text-3)]' },
            ].map(({ icon: Icon, value, label, color }) => (
              <div key={label} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">
                <Icon className={cn('w-3.5 h-3.5', color)} />
                <span className="text-[13px] font-semibold text-[var(--text-1)] tabular-nums">{value}</span>
                <span className="text-[12px] text-[var(--text-3)]">{label}</span>
              </div>
            ))}
          </div>

          <p className="text-[13px] text-[var(--text-3)] mb-6 max-w-lg">
            Connect services here for use in your agents. As super admin you can connect any service, including ones hidden from the user catalog.
          </p>

          {connectionsLoading || (statusesLoading && Object.keys(statuses).length === 0) ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-7 h-7 animate-spin text-violet-500" />
            </div>
          ) : (
            <div className="space-y-8">
              {groupedForConnections.map(([category, items]) => (
                <section key={category}>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-[var(--text-3)]">
                      {category}
                    </span>
                    <div className="flex-1 h-px bg-[var(--border)]" />
                    <span className="text-[11px] text-[var(--text-3)] tabular-nums">
                      {items.filter(c => statuses[c.id]?.connected).length}/{items.length}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {items.map(connector => {
                      const isConnected = statuses[connector.id]?.connected ?? false
                      const checkFailed = statuses[connector.id]?.checkFailed ?? false
                      // No entry yet for this id means its status hasn't resolved
                      // from the initial batch fetch (or a retry) yet.
                      const isChecking = statusesLoading && !statuses[connector.id]
                      const isDisconnecting = disconnectingId === connector.id
                      const isRetrying = retryingId === connector.id

                      return (
                        <div
                          key={connector.id}
                          className={cn(
                            'relative flex items-center gap-3 px-4 py-3.5 rounded-[var(--radius-lg)]',
                            'glass transition-[border-color,box-shadow] duration-200',
                            isConnected && 'border-l-2 border-l-green-500 bg-green-500/[0.025] dark:bg-green-500/[0.04]',
                          )}
                        >
                          <ConnectorLogo providerId={connector.provider_id} size="sm" className="shrink-0" />

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-[13px] font-medium text-[var(--text-1)] truncate">
                                {connector.name}
                              </span>
                              {!connector.is_visible && (
                                <Badge variant="neutral" className="text-[10px] shrink-0">hidden</Badge>
                              )}
                              {connector.available_actions.length > 0 && (
                                <button
                                  type="button"
                                  onClick={() => setActionsConnector(connector)}
                                  aria-label={`View ${connector.available_actions.length} available actions`}
                                  title={`${connector.available_actions.length} available action${connector.available_actions.length === 1 ? '' : 's'}`}
                                  className="flex items-center gap-1 h-4 shrink-0 px-1.5 rounded-full text-[9.5px] font-medium text-[var(--text-3)] hover:text-[var(--text-1)] bg-black/[0.03] dark:bg-white/[0.04] hover:bg-black/[0.05] dark:hover:bg-white/[0.08] transition-colors"
                                >
                                  <Info className="w-3 h-3 shrink-0" />
                                  {connector.available_actions.length}
                                </button>
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                              {isChecking ? (
                                <span className="flex items-center gap-1 text-[11px] text-[var(--text-3)]">
                                  <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                  Checking…
                                </span>
                              ) : checkFailed ? (
                                <button
                                  type="button"
                                  onClick={() => handleRetryStatus(connector.id)}
                                  disabled={isRetrying}
                                  className="flex items-center gap-1 text-[11px] text-amber-700 dark:text-amber-400 hover:underline disabled:opacity-60"
                                  title="Couldn't verify connection status — click to retry"
                                >
                                  <RefreshCw className={cn('w-2.5 h-2.5', isRetrying && 'animate-spin')} />
                                  Couldn't verify
                                </button>
                              ) : isConnected ? (
                                <span className="flex items-center gap-1 text-[11px] text-green-600 dark:text-green-400 font-medium">
                                  <CheckCircle2 className="w-2.5 h-2.5" />
                                  Connected
                                </span>
                              ) : (
                                <span className="text-[11px] text-[var(--text-3)]">Not connected</span>
                              )}
                              <span className="text-[var(--border-2)] select-none">·</span>
                              <span className="text-[11px] text-[var(--text-3)]">
                                {AUTH_TYPE_LABELS[connector.auth_type] ?? connector.auth_type}
                              </span>
                            </div>
                          </div>

                          <div className="shrink-0">
                            {isConnected ? (
                              <Button
                                variant="ghost"
                                size="xs"
                                onClick={() => handleDisconnect(connector)}
                                disabled={isDisconnecting}
                                className="text-[11px] text-[var(--text-3)] hover:text-red-500 hover:bg-red-500/10"
                              >
                                {isDisconnecting
                                  ? <Loader2 className="w-3 h-3 animate-spin" />
                                  : 'Disconnect'
                                }
                              </Button>
                            ) : (
                              <Button
                                size="xs"
                                onClick={() => setConnectTarget(connector)}
                                disabled={isChecking}
                                className="text-[11px]"
                              >
                                Connect
                              </Button>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Connect dialog */}
      {connectTarget && (
        <ConnectorSetupDialog
          connector={connectTarget}
          open
          onOpenChange={open => { if (!open) setConnectTarget(null) }}
          onConnected={handleConnected}
        />
      )}

      {/* Available actions dialog */}
      <Dialog
        open={!!actionsConnector}
        onOpenChange={open => { if (!open) setActionsConnector(null) }}
        title={actionsConnector ? `${actionsConnector.name} — Available actions` : ''}
        size="sm"
      >
        {actionsConnector && (
          <div className="space-y-1">
            <p className="text-[12.5px] text-[var(--text-3)] mb-3">
              Actions an agent can perform through this connector once it's connected.
            </p>
            <ul className="space-y-1.5">
              {actionsConnector.available_actions.map(action => (
                <li
                  key={action}
                  className="flex items-center gap-2 text-[13px] text-[var(--text-1)] bg-black/[0.03] dark:bg-white/[0.04] px-3 py-2 rounded-lg"
                >
                  <ListChecks className="w-3.5 h-3.5 shrink-0 text-[var(--text-3)]" />
                  {humanizeAction(action)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Dialog>
    </>
  )
}
