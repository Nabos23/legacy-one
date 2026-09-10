import { cn } from '@/lib/utils'

/**
 * ONE-AI brand mark — a flat "orchestration node" glyph (a supervisor node
 * routing to two agents), echoing the multi-agent product. No gradients.
 */
export function LogoMark({ className, size = 18 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M12 5.5 L6 17 M12 5.5 L18 17"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <circle cx="12" cy="5" r="2.7" fill="currentColor" />
      <circle cx="5.5" cy="18" r="2.3" fill="currentColor" />
      <circle cx="18.5" cy="18" r="2.3" fill="currentColor" />
    </svg>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span className="flex size-8 items-center justify-center rounded-[10px] bg-violet-600 glow-violet-sm">
        <LogoMark className="text-white" size={18} />
      </span>
      <span className="text-[15px] font-extrabold tracking-tight text-foreground">
        ONE<span className="text-violet-600 dark:text-violet-400">-AI</span>
      </span>
    </span>
  )
}
