import { cn } from '@/lib/utils'

interface ProgressProps {
  /** 0-100. Omit (or pass `undefined`) for an indeterminate sweep when the
   * total duration/size isn't known yet. */
  value?: number
  label?: string
  /** Show the "NN%" readout next to the label. Ignored while indeterminate. */
  showValue?: boolean
  className?: string
  barClassName?: string
}

/** Progress bar — for tasks with a knowable duration (uploads, downloads,
 * installs). Reaches for `Skeleton` instead if the whole thing is one
 * unknown-duration block, or an inline spinner for small contained actions. */
export function Progress({ value, label, showValue = true, className, barClassName }: ProgressProps) {
  const indeterminate = value === undefined
  const clamped = indeterminate ? 0 : Math.min(100, Math.max(0, value))

  return (
    <div className={cn('w-full', className)}>
      {(label || (showValue && !indeterminate)) && (
        <div className="flex items-center justify-between gap-2 mb-1.5">
          {label && <span className="text-[12px] text-[var(--text-3)] truncate">{label}</span>}
          {showValue && !indeterminate && (
            <span className="text-[12px] font-medium text-[var(--text-2)] tabular-nums shrink-0">
              {Math.round(clamped)}%
            </span>
          )}
        </div>
      )}
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={indeterminate ? undefined : Math.round(clamped)}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-1.5 w-full rounded-full bg-black/[0.07] dark:bg-white/[0.08] overflow-hidden"
      >
        <div
          className={cn(
            'h-full rounded-full bg-violet-600',
            indeterminate
              ? 'w-1/3 animate-progress-indeterminate'
              : 'w-full origin-left transition-transform duration-200 ease-out',
            barClassName,
          )}
          style={indeterminate ? undefined : { transform: `scaleX(${clamped / 100})` }}
        />
      </div>
    </div>
  )
}
