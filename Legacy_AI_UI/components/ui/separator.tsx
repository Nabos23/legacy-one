export function Separator({ className = '' }: { className?: string }) {
  return <div className={`h-px bg-[var(--border)] ${className}`} />
}
