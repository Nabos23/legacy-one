import { cn } from '@/lib/utils'

/** Elevated surface container. elevation 1 = default card, 2 = raised. */
export function Card({
  className,
  elevation = 1,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { elevation?: 1 | 2 }) {
  return <div className={cn(elevation === 2 ? 'card-2' : 'card-1', className)} {...props} />
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-5 py-4 border-b border-[var(--border)]', className)} {...props} />
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-h4 text-[var(--text-1)]', className)} {...props} />
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5', className)} {...props} />
}
