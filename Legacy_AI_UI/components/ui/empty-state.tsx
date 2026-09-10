import { LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 rounded-[var(--radius-lg)] bg-[var(--surface-2)] border border-dashed border-[var(--border-2)]">
      <div className="w-14 h-14 rounded-2xl bg-[var(--surface-3)] border border-[var(--border)] flex items-center justify-center mb-1">
        <Icon className="w-7 h-7 text-[var(--text-3)]" />
      </div>
      <h3 className="text-[16px] font-semibold mt-4">{title}</h3>
      {description && (
        <p className="text-[14px] text-[var(--text-3)] mt-2 max-w-[280px] text-center">
          {description}
        </p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
