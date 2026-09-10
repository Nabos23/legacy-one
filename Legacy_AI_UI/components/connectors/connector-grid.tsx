'use client'

import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { AlertCircle, PlugZap, Search, X, ArrowDownWideNarrow } from 'lucide-react'
import { connectorsApi } from '@/lib/api/connectors'
import { useConnectorStatuses } from '@/hooks/use-connector-statuses'
import { SearchInput } from '@/components/ui/search-input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Pagination } from '@/components/ui/pagination'
import { cn } from '@/lib/utils'
import type { ConnectorRegistryItem, ConnectorWithStatus } from '@/types/connectors'
import { ConnectorCard } from './connector-card'

const PAGE_SIZE_OPTIONS = [12, 24, 48]

export function ConnectorGrid() {
  const [registry, setRegistry] = useState<ConnectorRegistryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [connectedFirst, setConnectedFirst] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0])
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadRegistry = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRegistry(await connectorsApi.getRegistry())
    } catch {
      setError('Failed to load connectors.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadRegistry()
  }, [loadRegistry])

  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (searchDebounce.current) clearTimeout(searchDebounce.current)
    searchDebounce.current = setTimeout(() => { setSearch(val); setPage(1) }, 350)
  }

  const clearSearch = () => {
    setSearchInput('')
    setSearch('')
    setPage(1)
  }

  const toggleConnectedFirst = () => {
    setConnectedFirst(v => !v)
    setPage(1)
  }

  const connectorIds = useMemo(() => registry.map(c => c.id), [registry])
  const { statuses, loading: statusesLoading, setStatus, retryOne } = useConnectorStatuses(connectorIds)

  const connectors: ConnectorWithStatus[] = registry.map(c => ({
    ...c,
    status: statuses[c.id] ?? null,
    statusLoading: statusesLoading && !statuses[c.id],
  }))

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    let list = connectors
    if (q) {
      list = list.filter(c =>
        c.name.toLowerCase().includes(q)
        || c.description.toLowerCase().includes(q)
        || c.category.toLowerCase().includes(q)
      )
    }
    if (connectedFirst) {
      list = [...list].sort((a, b) => Number(b.status?.connected ?? false) - Number(a.status?.connected ?? false))
    } else {
      list = [...list].sort((a, b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name))
    }
    return list
  }, [connectors, search, connectedFirst])

  const paged = useMemo(
    () => filtered.slice((page - 1) * pageSize, page * pageSize),
    [filtered, page, pageSize],
  )

  if (loading) {
    return (
      <div className="space-y-10">
        <div className="flex gap-3">
          <Skeleton className="h-9 flex-1 max-w-xs" />
          <Skeleton className="h-9 w-32" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[180px] rounded-2xl" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center rounded-[var(--radius-lg)] bg-[var(--surface-2)] border border-dashed border-[var(--border-2)]">
        <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
          <AlertCircle className="w-6 h-6 text-red-500 dark:text-red-400" />
        </div>
        <p className="text-[16px] font-semibold text-[var(--text-1)]">Couldn&rsquo;t load connectors</p>
        <p className="text-[14px] text-[var(--text-3)] mt-2 max-w-md">{error}</p>
        <Button variant="secondary" size="sm" className="mt-4" onClick={loadRegistry}>
          Try again
        </Button>
      </div>
    )
  }

  if (connectors.length === 0) {
    return (
      <EmptyState
        icon={PlugZap}
        title="No connectors available"
        description="Check back later, or contact your admin if you expected connectors here."
      />
    )
  }

  const connectedCount = connectors.filter(c => c.status?.connected).length

  return (
    <div className="space-y-10">
      {/* Search + sort + summary */}
      <div className="flex items-center gap-3 flex-wrap">
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

        <button
          type="button"
          onClick={toggleConnectedFirst}
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium border transition-colors duration-100',
            connectedFirst
              ? 'bg-violet-600 text-white border-violet-600'
              : 'bg-[var(--surface-2)] text-[var(--text-3)] border-[var(--border)] hover:text-[var(--text-2)] hover:border-[var(--border-2)]',
          )}
        >
          <ArrowDownWideNarrow className="w-3 h-3" />
          Connected first
        </button>

        <div className="flex items-center gap-3 text-[13px] text-[var(--text-3)] ml-auto">
          <span className="font-medium text-[var(--text-1)]">{connectors.length}</span> connectors available
          {connectedCount > 0 && (
            <>
              <span className="w-1 h-1 rounded-full bg-[var(--text-3)]/30" />
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.6)]" />
                <span className="font-medium text-green-600 dark:text-green-400">{connectedCount}</span> connected
              </span>
            </>
          )}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No matching connectors"
          description="Try a different search term."
          action={<Button variant="secondary" size="sm" onClick={clearSearch}>Clear search</Button>}
        />
      ) : (
        <>
          {/* Category sections, but only for the connectors on the current page */}
          {Array.from(new Set(paged.map(c => c.category))).map(category => (
            <section key={category}>
              <div className="flex items-center gap-3 mb-4">
                <h2 className="text-[11px] font-bold tracking-[0.12em] uppercase text-[var(--text-3)]">
                  {category}
                </h2>
                <div className="flex-1 h-px bg-[var(--border)]" />
                <span className="text-[11px] text-[var(--text-3)]">
                  {filtered.filter(c => c.category === category).length}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {paged
                  .filter(c => c.category === category)
                  .map(connector => (
                    <ConnectorCard
                      key={connector.id}
                      connector={connector}
                      onStatusChange={() => retryOne(connector.id)}
                      onOptimisticStatus={status => setStatus(connector.id, status)}
                    />
                  ))}
              </div>
            </section>
          ))}

          <Pagination
            page={page}
            pageSize={pageSize}
            total={filtered.length}
            onPageChange={setPage}
            onPageSizeChange={ps => { setPageSize(ps); setPage(1) }}
            pageSizeOptions={PAGE_SIZE_OPTIONS}
          />
        </>
      )}
    </div>
  )
}
