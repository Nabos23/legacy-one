'use client'

import { cn } from '@/lib/utils'

interface ToggleProps {
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
  className?: string
  'aria-label'?: string
}

/** Accessible on/off switch with the violet accent. Replaces native checkboxes for preferences. */
export function Toggle({ checked, onChange, disabled, className, ...props }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full outline-none transition-colors duration-200',
        'focus-visible:ring-4 focus-visible:ring-violet-500/20 disabled:opacity-50 disabled:pointer-events-none',
        checked ? 'bg-violet-600' : 'bg-black/[0.12] dark:bg-white/[0.15]',
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          'inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)]',
          checked ? 'translate-x-[22px]' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}
