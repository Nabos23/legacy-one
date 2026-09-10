import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

type IconTileColor = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'
type IconTileSize = 'sm' | 'md' | 'lg'

/** Shared color map — kept in sync with StatsCard's tile colors for a single icon language. */
const colorMap: Record<IconTileColor, string> = {
  primary: 'bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400',
  success: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
  warning: 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
  danger:  'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
  info:    'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-600 dark:text-cyan-400',
  neutral: 'bg-black/[0.04] dark:bg-white/[0.06] text-[var(--text-2)]',
}

const sizeMap: Record<IconTileSize, string> = {
  sm: 'w-8 h-8 rounded-lg [&_svg]:w-4 [&_svg]:h-4',
  md: 'w-10 h-10 rounded-xl [&_svg]:w-5 [&_svg]:h-5',
  lg: 'w-12 h-12 rounded-2xl [&_svg]:w-6 [&_svg]:h-6',
}

interface IconTileProps {
  icon: LucideIcon
  color?: IconTileColor
  size?: IconTileSize
  className?: string
}

/** The recurring violet (or semantic) rounded icon box used across landing + dashboard. */
export function IconTile({ icon: Icon, color = 'primary', size = 'md', className }: IconTileProps) {
  return (
    <div className={cn('flex items-center justify-center shrink-0', sizeMap[size], colorMap[color], className)}>
      <Icon />
    </div>
  )
}
