'use client'

import { Trash2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface BulkDeleteButtonProps {
  /** Number of selected rows, shown in the label (e.g. "Delete 3"). */
  count: number
  busy?: boolean
  onClick: () => void
  /** Verb shown in the label — defaults to "Delete", pass "Remove" etc. for entities that use different wording. */
  label?: string
  busyLabel?: string
  className?: string
}

/** Solid, icon-led destructive action for a DataTable bulk-selection bar —
 * a clearer destructive affordance than a plain text button for an action
 * that can hit many rows at once. */
export function BulkDeleteButton({
  count,
  busy = false,
  onClick,
  label = 'Delete',
  busyLabel,
  className,
}: BulkDeleteButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className={cn(
        'inline-flex items-center gap-1.5 h-7 pl-2.5 pr-3 rounded-lg text-[12.5px] font-medium',
        'bg-red-600 text-white shadow-sm shadow-red-600/20',
        'hover:bg-red-700 active:bg-red-800 active:translate-y-px',
        'transition-[background-color,transform] duration-[120ms] ease-[cubic-bezier(0.16,1,0.3,1)]',
        'disabled:opacity-60 disabled:pointer-events-none',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/50',
        className,
      )}
    >
      {busy ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <Trash2 className="w-3.5 h-3.5" />
      )}
      {busy ? (busyLabel ?? 'Deleting…') : `${label} ${count}`}
    </button>
  )
}
