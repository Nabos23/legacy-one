'use client'

import { useState } from 'react'
import { Info, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  title: string
  steps: string[]
  defaultOpen?: boolean
}

/**
 * A collapsible "how this works" callout, styled like the connector setup
 * guide's blue instructions box (components/connectors/connector-setup-dialog.tsx)
 * so the two features read as one system. Unlike connectors — where each
 * provider has its own registry-driven setup_guide — MCP servers are
 * generic BYO, so this explains the shared two-step model (connect, then
 * attach) rather than any one server's specific setup.
 */
export function McpInfoCard({ title, steps, defaultOpen = true }: Props) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="rounded-xl border border-blue-200/60 dark:border-blue-800/40 bg-blue-50/60 dark:bg-blue-950/20 mb-5">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-2 px-4 py-3"
      >
        <span className="flex items-center gap-2 text-[12px] font-semibold text-blue-700 dark:text-blue-300 uppercase tracking-wide">
          <Info className="w-3.5 h-3.5" />
          {title}
        </span>
        {open ? (
          <ChevronUp className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
        )}
      </button>
      <div className={cn('overflow-hidden transition-[max-height]', open ? 'max-h-[600px]' : 'max-h-0')}>
        <ol className="space-y-2 px-4 pb-4">
          {steps.map((step, i) => (
            <li key={i} className="flex gap-2.5">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 text-[10px] font-bold flex items-center justify-center mt-0.5">
                {i + 1}
              </span>
              <span className="text-[12px] text-blue-900 dark:text-blue-200 leading-relaxed">
                {step}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
