import { Info } from 'lucide-react'
import { cn } from '@/lib/utils'

interface InfoBoxProps {
  variant?: 'info' | 'warning' | 'error' | 'success'
  children: React.ReactNode
  className?: string
}

export function InfoBox({
  variant = 'info',
  children,
  className,
}: InfoBoxProps) {
  const variants = {
    info: 'border-l-4 border-cyan-500 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
    warning: 'border-l-4 border-amber-500 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    error: 'border-l-4 border-red-500 bg-red-500/10 text-red-700 dark:text-red-300',
    success: 'border-l-4 border-green-500 bg-green-500/10 text-green-700 dark:text-green-300',
  }

  return (
    <div
      className={cn(
        'flex gap-3 p-3 rounded-[var(--radius-md)]',
        variants[variant],
        className
      )}
    >
      <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
      <div className="text-[13px] leading-relaxed">{children}</div>
    </div>
  )
}
