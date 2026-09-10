'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { ChevronRight, ArrowRight, X } from 'lucide-react'
import { SearchInput } from '@/components/ui/search-input'
import { Badge } from '@/components/ui/badge'
import { IconTile } from '@/components/ui/icon-tile'
import { SettingsCard } from '@/components/settings/settings-card'
import type { HelpTopic } from '@/lib/help-content'
import { cn } from '@/lib/utils'

/** Searchable, grouped-by-category list of feature guide entries — covers every module in the product. */
export function HelpTopics({ topics }: { topics: HelpTopic[] }) {
  const [query, setQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [openTitle, setOpenTitle] = useState<string | null>(topics[0]?.title ?? null)

  const categories = useMemo(() => Array.from(new Set(topics.map(t => t.category))), [topics])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return topics.filter(t => {
      if (activeCategory && t.category !== activeCategory) return false
      if (!q) return true
      return (
        t.title.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        t.category.toLowerCase().includes(q)
      )
    })
  }, [topics, query, activeCategory])

  const grouped = useMemo(() => {
    const map = new Map<string, HelpTopic[]>()
    for (const t of filtered) {
      const list = map.get(t.category) ?? []
      list.push(t)
      map.set(t.category, list)
    }
    return Array.from(map.entries())
  }, [filtered])

  return (
    <SettingsCard>
      <div className="flex items-center justify-between gap-4 mb-1">
        <div>
          <h3 className="text-[16px] font-semibold text-[var(--text-1)]">Feature Guide</h3>
          <p className="text-[13px] text-[var(--text-3)]">Everything the platform can do, by module</p>
        </div>
        <Badge variant="neutral" className="shrink-0">{filtered.length} topics</Badge>
      </div>

      <SearchInput
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search features…"
        rightElement={
          query ? (
            <button type="button" onClick={() => setQuery('')} aria-label="Clear search">
              <X className="w-3.5 h-3.5 hover:text-[var(--text-1)]" />
            </button>
          ) : undefined
        }
        className="mt-4 mb-3"
      />

      <div className="flex flex-wrap gap-1.5 mb-6">
        <button
          type="button"
          onClick={() => setActiveCategory(null)}
          className={cn(
            'px-2.5 py-1 rounded-full text-[12px] font-medium border transition-colors',
            activeCategory === null
              ? 'bg-violet-500/10 border-violet-500/30 text-violet-600 dark:text-violet-400'
              : 'border-[var(--border)] text-[var(--text-3)] hover:text-[var(--text-1)]',
          )}
        >
          All
        </button>
        {categories.map(cat => (
          <button
            key={cat}
            type="button"
            onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
            className={cn(
              'px-2.5 py-1 rounded-full text-[12px] font-medium border transition-colors',
              activeCategory === cat
                ? 'bg-violet-500/10 border-violet-500/30 text-violet-600 dark:text-violet-400'
                : 'border-[var(--border)] text-[var(--text-3)] hover:text-[var(--text-1)]',
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {grouped.length === 0 && (
        <p className="text-[13px] text-[var(--text-3)] text-center py-8">No topics match &ldquo;{query}&rdquo;.</p>
      )}

      <div className="space-y-6">
        {grouped.map(([category, items]) => (
          <div key={category}>
            <h4 className="text-[11px] font-bold uppercase tracking-wide text-[var(--text-3)] mb-2.5">
              {category}
            </h4>
            <div className="space-y-2">
              {items.map(t => {
                const isOpen = openTitle === t.title
                return (
                  <div
                    key={t.title}
                    className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => setOpenTitle(isOpen ? null : t.title)}
                      aria-expanded={isOpen}
                      className="flex w-full items-center gap-3 p-3.5 text-left"
                    >
                      <IconTile icon={t.icon} color={t.color} size="sm" />
                      <span className="flex-1 text-[13.5px] font-medium text-[var(--text-1)]">{t.title}</span>
                      <ChevronRight
                        className={cn(
                          'w-4 h-4 text-[var(--text-3)] transition-transform shrink-0',
                          isOpen && 'rotate-90',
                        )}
                      />
                    </button>
                    <div
                      className={cn(
                        'grid transition-[grid-template-rows] duration-200 ease-out',
                        isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
                      )}
                    >
                      <div className="overflow-hidden">
                        <div className="px-3.5 pb-3.5 pl-[3.25rem]">
                          <p className="text-[13px] leading-relaxed text-[var(--text-2)]">{t.description}</p>
                          {t.href && (
                            <Link
                              href={t.href}
                              className="inline-flex items-center gap-1 mt-2 text-[12.5px] font-medium text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300"
                            >
                              Go there <ArrowRight className="w-3.5 h-3.5" />
                            </Link>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </SettingsCard>
  )
}
