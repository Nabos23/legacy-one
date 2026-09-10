'use client'

import Link from 'next/link'
import { Home, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Crumb {
  label: string
  href?: string
}

/** Build breadcrumb items from a pathname. The root segment links to its dashboard.
 * `labels` maps a raw segment (e.g. a Mongo id) to a display name — registered by
 * the page that loaded the entity, via `useBreadcrumbLabel` — so a dynamic route
 * segment shows "multi-branch check" instead of the raw id. */
export function crumbsFromPath(pathname: string, labels: Record<string, string> = {}): Crumb[] {
  const segs = pathname.split('/').filter(Boolean)
  if (segs.length === 0) return []
  const items: Crumb[] = []
  let acc = ''
  segs.forEach((seg, i) => {
    acc += '/' + seg
    const label =
      labels[seg] ??
      (i === 0
        ? seg === 'admin'
          ? 'Admin'
          : 'Client'
        : seg.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '))
    const href = i === 0 ? `/${seg}/dashboard` : acc
    items.push({ label, href })
  })
  return items
}

export function Breadcrumb({ items, className }: { items: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-1.5 text-[13px] min-w-0 select-none', className)}>
      {items.map((c, i) => {
        const last = i === items.length - 1
        const isRoot = i === 0

        return (
          <span key={i} className="flex items-center gap-1.5 min-w-0">
            {i > 0 && <ChevronRight className="w-3.5 h-3.5 text-[var(--text-3)] shrink-0" />}
            {isRoot ? (
              c.href ? (
                <Link
                  href={c.href}
                  aria-label={c.label}
                  title={c.label}
                  className="flex items-center text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors duration-[120ms] shrink-0"
                >
                  <Home className="w-3.5 h-3.5" />
                </Link>
              ) : (
                <span aria-label={c.label} title={c.label} className="flex items-center text-[var(--text-3)] shrink-0">
                  <Home className="w-3.5 h-3.5" />
                </span>
              )
            ) : c.href && !last ? (
              <Link
                href={c.href}
                className="text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors duration-[120ms] truncate max-w-[160px]"
              >
                {c.label}
              </Link>
            ) : (
              <span
                className={cn(
                  'truncate max-w-[220px]',
                  last ? 'text-violet-600 dark:text-violet-400 font-semibold' : 'text-[var(--text-3)]',
                )}
                title={c.label}
              >
                {c.label}
              </span>
            )}
          </span>
        )
      })}
    </nav>
  )
}
