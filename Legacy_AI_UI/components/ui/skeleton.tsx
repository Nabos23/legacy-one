import { cn } from '@/lib/utils'

export function Skeleton({
  className,
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-black/[0.07] dark:bg-white/[0.08]',
        className
      )}
    />
  )
}
