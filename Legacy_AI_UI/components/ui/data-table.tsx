'use client'

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Package, ChevronUp, ChevronDown, ChevronsUpDown, AlertCircle, type LucideIcon } from 'lucide-react'
import { Skeleton } from './skeleton'
import { EmptyState } from './empty-state'
import { Checkbox } from './checkbox'
import { Button } from './button'
import { Pagination, type PaginationProps } from './pagination'
import { cn } from '@/lib/utils'

export interface Column<T> {
  key: string
  header: string
  render?: (row: T, index: number) => React.ReactNode
  className?: string
  /** Enables click-to-sort on this column header (sorts the current page). */
  sortable?: boolean
  /** Value used for sorting; defaults to row[key]. */
  sortAccessor?: (row: T) => string | number | null | undefined
  align?: 'left' | 'right' | 'center'
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  emptyMessage?: string
  emptyDescription?: string
  emptyIcon?: LucideIcon
  emptyAction?: React.ReactNode
  isLoading?: boolean
  /** When set, an error card with a retry button is shown instead of the table. */
  error?: string | null
  onRetry?: () => void
  /** Provide a stable id per row to enable selection. */
  getRowId?: (row: T) => string
  /** Renders the bulk-action bar contents when one or more rows are selected. */
  bulkActions?: (ctx: { ids: string[]; clear: () => void }) => React.ReactNode
  /** When provided, an integrated footer pager is rendered. */
  pagination?: PaginationProps
  /** Controlled (server-side) sort. When provided alongside `onSortChange`,
   * the table stops managing its own sort state / re-sorting `data` itself —
   * it just reflects `sortState` and calls `onSortChange` on header clicks,
   * trusting the caller to have already fetched `data` pre-sorted. Omit both
   * for the default client-side sort (sorts only the current page). */
  sortState?: SortState
  onSortChange?: (next: SortState) => void
}

export type SortState = { key: string; dir: 'asc' | 'desc' } | null

function compareValues(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0
  if (a == null) return -1
  if (b == null) return 1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' })
}

export function DataTable<T>({
  columns,
  data,
  emptyMessage = 'No data available',
  emptyDescription,
  emptyIcon,
  emptyAction,
  isLoading = false,
  error = null,
  onRetry,
  getRowId,
  bulkActions,
  pagination,
  sortState,
  onSortChange,
}: DataTableProps<T>) {
  const selectable = !!getRowId && !!bulkActions
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [internalSort, setInternalSort] = useState<SortState>(null)
  const controlledSort = sortState !== undefined && !!onSortChange
  const sort = controlledSort ? sortState! : internalSort

  const rowIds = useMemo(() => (getRowId ? data.map(getRowId) : []), [data, getRowId])
  const rowIdsKey = rowIds.join('|')

  // Prune selections that are no longer on the loaded page (e.g. after paging or refetch).
  useEffect(() => {
    if (!selectable) return
    setSelected(prev => {
      const next = new Set([...prev].filter(id => rowIds.includes(id)))
      return next.size === prev.size ? prev : next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowIdsKey, selectable])

  const sortedData = useMemo(() => {
    // Controlled mode: the caller already fetched `data` sorted server-side —
    // sorting it again client-side here would just re-shuffle the current page.
    if (controlledSort) return data
    if (!sort) return data
    const col = columns.find(c => c.key === sort.key)
    if (!col) return data
    const accessor = col.sortAccessor ?? ((row: T) => (row as Record<string, unknown>)[col.key])
    const copy = [...data]
    copy.sort((a, b) => {
      const res = compareValues(accessor(a), accessor(b))
      return sort.dir === 'asc' ? res : -res
    })
    return copy
  }, [data, sort, columns, controlledSort])

  const totalCols = columns.length + (selectable ? 1 : 0)

  // FLIP-animate row reordering on sort — otherwise rows teleport into their new
  // positions with no transition (AUDIT.md category 8: a state change that
  // teleports where a brief transition would prevent a jarring change).
  const rowElsRef = useRef<Map<string, HTMLTableRowElement>>(new Map())
  const prevRectsRef = useRef<Map<string, DOMRect>>(new Map())
  useLayoutEffect(() => {
    const newRects = new Map<string, DOMRect>()
    rowElsRef.current.forEach((el, id) => newRects.set(id, el.getBoundingClientRect()))
    prevRectsRef.current.forEach((oldRect, id) => {
      const el = rowElsRef.current.get(id)
      const newRect = newRects.get(id)
      if (!el || !newRect) return
      const deltaY = oldRect.top - newRect.top
      if (!deltaY) return
      el.style.transition = 'none'
      el.style.transform = `translateY(${deltaY}px)`
      el.getBoundingClientRect() // force reflow before re-enabling the transition
      requestAnimationFrame(() => {
        el.style.transition = 'transform 220ms cubic-bezier(0.16,1,0.3,1)'
        el.style.transform = ''
      })
    })
    prevRectsRef.current = newRects
  }, [sortedData])

  const nextSortState = (prev: SortState, key: string): SortState => {
    if (!prev || prev.key !== key) return { key, dir: 'asc' }
    if (prev.dir === 'asc') return { key, dir: 'desc' }
    return null
  }

  const toggleSort = (key: string) => {
    if (controlledSort) {
      onSortChange!(nextSortState(sort, key))
      return
    }
    setInternalSort(prev => nextSortState(prev, key))
  }

  if (error) {
    return (
      <div className="glass overflow-hidden rounded-[var(--radius-lg)]">
        <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
            <AlertCircle className="w-6 h-6 text-red-500 dark:text-red-400" />
          </div>
          <p className="text-[16px] font-semibold text-[var(--text-1)]">Couldn&rsquo;t load data</p>
          <p className="text-[14px] text-[var(--text-3)] mt-2 max-w-md">{error}</p>
          {onRetry && (
            <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="glass overflow-hidden rounded-[var(--radius-lg)]">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[var(--surface-2)] border-b">
              <tr>
                {selectable && <th className="w-10 px-4 py-3" />}
                {columns.map(col => (
                  <th
                    key={col.key}
                    className="px-4 py-3 text-left text-[11px] uppercase tracking-wider text-[var(--text-3)] font-medium"
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-[var(--border)]">
                  {selectable && (
                    <td className="px-4 py-3.5">
                      <Skeleton className="h-5 w-5 rounded-md" />
                    </td>
                  )}
                  {columns.map(col => (
                    <td key={col.key} className="px-4 py-3.5">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <EmptyState
        icon={emptyIcon ?? Package}
        title={emptyMessage}
        description={emptyDescription}
        action={emptyAction}
      />
    )
  }

  const allSelected = selectable && rowIds.length > 0 && rowIds.every(id => selected.has(id))

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(rowIds))
  }

  const toggleOne = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const alignClass = (align?: string) =>
    align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'

  return (
    <div className="glass overflow-hidden rounded-[var(--radius-lg)]">
      {selectable && selected.size > 0 && (
        <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-violet-50 dark:bg-violet-500/10 border-b border-violet-100 dark:border-violet-500/20">
          <span className="text-[13px] font-medium text-violet-700 dark:text-violet-300">
            {selected.size} selected
          </span>
          <div className="flex items-center gap-2">
            {bulkActions!({ ids: [...selected], clear: () => setSelected(new Set()) })}
            <Button variant="ghost" size="xs" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-[var(--surface-2)] border-b">
            <tr>
              {selectable && (
                <th className="w-10 px-4 py-3">
                  <Checkbox checked={!!allSelected} onChange={toggleAll} aria-label="Select all rows" />
                </th>
              )}
              {columns.map(col => {
                const isSorted = sort?.key === col.key
                return (
                  <th
                    key={col.key}
                    className={cn(
                      'px-4 py-3 text-[11px] uppercase tracking-wider text-[var(--text-3)] font-medium border-b border-[var(--border)]',
                      alignClass(col.align),
                    )}
                  >
                    {col.sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(col.key)}
                        className="inline-flex items-center gap-1 hover:text-[var(--text-1)] transition-colors uppercase tracking-wider"
                      >
                        {col.header}
                        {isSorted ? (
                          sort!.dir === 'asc' ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )
                        ) : (
                          <ChevronsUpDown className="w-3.5 h-3.5 opacity-40" />
                        )}
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {sortedData.map((row, rowIndex) => {
              const id = getRowId ? getRowId(row) : String(rowIndex)
              const isSelected = selectable && selected.has(id)
              return (
                <tr
                  key={id}
                  ref={el => {
                    if (el) rowElsRef.current.set(id, el)
                    else rowElsRef.current.delete(id)
                  }}
                  className={cn(
                    'border-b border-[var(--border)] last:border-0 transition-colors',
                    isSelected
                      ? 'bg-violet-50/60 dark:bg-violet-500/[0.07]'
                      : 'hover:bg-black/[0.02] dark:hover:bg-white/[0.02]',
                  )}
                >
                  {selectable && (
                    <td className="px-4 py-3.5">
                      <Checkbox
                        checked={!!isSelected}
                        onChange={() => toggleOne(id)}
                        aria-label="Select row"
                      />
                    </td>
                  )}
                  {columns.map(col => (
                    <td
                      key={col.key}
                      className={cn('px-4 py-3.5 text-[14px] text-[var(--text-2)]', alignClass(col.align), col.className)}
                    >
                      {col.render ? col.render(row, rowIndex) : String((row as Record<string, unknown>)[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {pagination && pagination.total > pagination.pageSize && <Pagination {...pagination} />}
    </div>
  )
}
