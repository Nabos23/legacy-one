import { cn } from '@/lib/utils'

interface RevealProps {
  children: React.ReactNode
  /** Stagger delay in milliseconds. */
  delay?: number
  className?: string
}

/**
 * Subtle staggered entrance (slide-up + fade) matching the client dashboard.
 * Wrap each major page section and pass an incremental `delay` for the cascade.
 */
export function Reveal({ children, delay = 0, className }: RevealProps) {
  return (
    <div className={cn('animate-slideUpFade', className)} style={{ animationDelay: `${delay}ms` }}>
      {children}
    </div>
  )
}
