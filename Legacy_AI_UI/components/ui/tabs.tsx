'use client'

import { useLayoutEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

export interface TabItem {
  value: string
  label: React.ReactNode
}

interface TabsProps {
  tabs: TabItem[]
  value: string
  onChange: (value: string) => void
  className?: string
  /** Stretch tabs to fill the container equally instead of hugging each
   * label's own width. Use for a small fixed set meant to span a container
   * evenly (e.g. a 2-way toggle) — default hugs content, since a pill nav
   * with varied label lengths should never squeeze a longer label down to
   * match a shorter one. */
  equalWidth?: boolean
}

/** Segmented control style tabs. A single pill slides between tabs via
 * `transform` (AUDIT.md category 8 — connects the two states spatially
 * instead of each button independently swapping its own background). */
export function Tabs({ tabs, value, onChange, className, equalWidth }: TabsProps) {
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const [pill, setPill] = useState<{ x: number; width: number } | null>(null)

  useLayoutEffect(() => {
    const el = buttonRefs.current.get(value)
    if (el) setPill({ x: el.offsetLeft, width: el.offsetWidth })
  }, [value, tabs])

  return (
    <div
      role="tablist"
      className={cn(
        'relative inline-flex items-center gap-1 p-1.5 rounded-full bg-[var(--surface-2)] border border-[var(--border)]',
        className,
      )}
    >
      {pill && (
        <div
          className="absolute inset-y-1.5 rounded-full bg-[var(--surface)] shadow-[0_1px_3px_rgba(0,0,0,0.08)] dark:shadow-[0_1px_3px_rgba(0,0,0,0.35)] transition-[transform,width] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)]"
          style={{ width: pill.width, transform: `translateX(${pill.x - 6}px)` }}
        />
      )}
      {tabs.map(t => (
        <button
          key={t.value}
          ref={el => {
            if (el) buttonRefs.current.set(t.value, el)
            else buttonRefs.current.delete(t.value)
          }}
          type="button"
          role="tab"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            'relative z-10 px-4 py-2 rounded-full text-[13px] transition-colors duration-[120ms] whitespace-nowrap text-center truncate',
            equalWidth && 'flex-1',
            value === t.value ? 'font-semibold text-[var(--text-1)]' : 'font-medium text-[var(--text-3)] hover:text-[var(--text-1)]',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
