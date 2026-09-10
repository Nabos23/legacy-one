import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IconTile } from '@/components/ui/icon-tile'

/** Shared card shell — matches the landing page's glass language for a consistent premium feel. */
export function SettingsCard({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        'glass-card rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-2xl backdrop-saturate-150 p-7',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function SettingsCardHeader({
  icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        <IconTile icon={icon} size="md" />
        <div>
          <h3 className="text-[16px] font-semibold text-[var(--text-1)]">{title}</h3>
          <p className="text-[13px] text-[var(--text-3)]">{description}</p>
        </div>
      </div>
      {action}
    </div>
  )
}
