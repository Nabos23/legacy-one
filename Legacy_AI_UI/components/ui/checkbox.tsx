'use client'

import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CheckboxProps {
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
  className?: string
  'aria-label'?: string
}

/** Accessible checkbox with the violet accent and a visible focus ring. */
export function Checkbox({ checked, onChange, disabled, className, ...props }: CheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'flex h-5 w-5 shrink-0 items-center justify-center rounded-md border outline-none transition-[background-color,border-color,box-shadow] duration-150 active:scale-[0.94]',
        'focus-visible:ring-4 focus-visible:ring-violet-500/20 disabled:opacity-50 disabled:pointer-events-none',
        checked
          ? 'bg-violet-600 border-violet-600 text-white'
          : 'bg-transparent border-[var(--border)] hover:border-violet-400 dark:hover:border-violet-500',
        className,
      )}
      {...props}
    >
      {checked && <Check className="w-3.5 h-3.5 animate-scaleIn" strokeWidth={3} />}
    </button>
  )
}
