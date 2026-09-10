import { cn } from '@/lib/utils'

interface StatusIndicatorProps {
  status: 'active' | 'inactive' | 'warning' | 'error' | 'processing'
  label?: string
  pulse?: boolean
}

export function StatusIndicator({
  status,
  label,
  pulse = false,
}: StatusIndicatorProps) {
  const colorMap = {
    active: 'bg-green-400',
    inactive: 'bg-zinc-500',
    warning: 'bg-amber-400',
    error: 'bg-red-400',
    processing: 'bg-cyan-400',
  }

  const dotClass = cn(
    'w-2 h-2 rounded-full',
    colorMap[status],
    pulse && 'animate-pulse'
  )

  if (!label) {
    return <div className={dotClass} />
  }

  return (
    <div className="flex items-center gap-2">
      <div className={dotClass} />
      <span className="text-[12px] text-[var(--text-3)]">{label}</span>
    </div>
  )
}
