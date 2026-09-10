'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'

interface TooltipProps {
  content: React.ReactNode
  children: React.ReactNode
  side?: 'top' | 'bottom'
  className?: string
}

/** Lightweight hover/focus tooltip — no portal, positions relative to the trigger. */
export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const [show, setShow] = useState(false)
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
    >
      {children}
      {show && content && (
        <span
          role="tooltip"
          className={cn(
            'animate-scaleIn absolute z-[60] left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[11px] font-medium pointer-events-none',
            'bg-[var(--text-1)] text-[var(--surface)] shadow-[0_10px_24px_-8px_rgba(0,0,0,0.35)]',
            /* Scale from the edge touching the trigger, not the tooltip's own center (AUDIT.md category 3). */
            side === 'top' ? 'bottom-full mb-2 origin-bottom' : 'top-full mt-2 origin-top',
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}
