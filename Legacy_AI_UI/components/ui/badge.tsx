import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium',
  {
    variants: {
      variant: {
        primary: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
        success: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
        warning: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
        danger:  'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
        info:    'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
        neutral: 'bg-[var(--surface-2)] text-[var(--text-2)] border border-[var(--border)]',
        outline: 'border border-[var(--border-2)] text-[var(--text-2)]',
      },
    },
    defaultVariants: {
      variant: 'neutral',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
