'use client'

import { useId } from 'react'
import { motion, LayoutGroup } from 'motion/react'
import { Select } from './select'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  /** When provided, a page-size selector is shown. */
  onPageSizeChange?: (size: number) => void
  pageSizeOptions?: number[]
}

type PageItem = number | 'ellipsis'

function range(start: number, end: number): number[] {
  if (end < start) return []
  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
}

/** Windowed page list, e.g. page=4 of 12 -> [1, 'ellipsis', 3, 4, 5, 'ellipsis', 12].
 * Near either edge the window doesn't shrink — it slides to keep 5 numbers visible. */
function getPageItems(page: number, count: number): PageItem[] {
  if (count <= 7) return range(1, count)
  if (page <= 4) return [...range(1, 5), 'ellipsis', count]
  if (page >= count - 3) return [1, 'ellipsis', ...range(count - 4, count)]
  return [1, 'ellipsis', page - 1, page, page + 1, 'ellipsis', count]
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
}: PaginationProps) {
  const groupId = useId()
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, total)
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const items = getPageItems(page, totalPages)

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t border-[var(--border)]">
      <div className="flex items-center gap-3">
        <span className="text-[13px] text-[var(--text-3)]">
          Showing {startItem}–{endItem} of {total}
        </span>
        {onPageSizeChange && (
          <label className="hidden sm:flex items-center gap-1.5 text-[13px] text-[var(--text-3)]">
            <span>Rows:</span>
            <Select
              value={String(pageSize)}
              onValueChange={v => onPageSizeChange(Number(v))}
              className="h-7 w-16 px-1.5 text-[13px]"
              options={pageSizeOptions.map(opt => ({ value: String(opt), label: String(opt) }))}
            />
          </label>
        )}
      </div>

      <LayoutGroup id={groupId}>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--text-3)] transition-colors hover:bg-black/[0.05] hover:text-[var(--text-1)] disabled:opacity-40 disabled:pointer-events-none dark:hover:bg-white/[0.07]"
            aria-label="Previous page"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {items.map((item, i) =>
            item === 'ellipsis' ? (
              <span
                key={`ellipsis-${i}`}
                className="flex h-8 w-8 shrink-0 items-center justify-center text-[13px] text-[var(--text-3)]"
              >
                …
              </span>
            ) : (
              <button
                key={item}
                type="button"
                onClick={() => onPageChange(item)}
                aria-current={item === page ? 'page' : undefined}
                className={cn(
                  'relative flex h-8 min-w-8 shrink-0 items-center justify-center rounded-lg px-2 text-[13px] font-medium transition-colors',
                  item === page
                    ? 'text-white'
                    : 'text-[var(--text-2)] hover:bg-black/[0.05] hover:text-[var(--text-1)] dark:hover:bg-white/[0.07]',
                )}
              >
                {item === page && (
                  <motion.span
                    layoutId={`${groupId}-active-page`}
                    className="absolute inset-0 rounded-lg bg-violet-600"
                    transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                  />
                )}
                <span className="relative z-10">{item}</span>
              </button>
            ),
          )}

          <button
            type="button"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--text-3)] transition-colors hover:bg-black/[0.05] hover:text-[var(--text-1)] disabled:opacity-40 disabled:pointer-events-none dark:hover:bg-white/[0.07]"
            aria-label="Next page"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </LayoutGroup>
    </div>
  )
}
