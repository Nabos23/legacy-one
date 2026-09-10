interface PageHeaderProps {
  title: string
  description?: string
  eyebrow?: string
  actions?: React.ReactNode
}

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
}: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        {eyebrow && (
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-violet-600 dark:text-violet-400 mb-2">
            {eyebrow}
          </p>
        )}
        <h1 className="text-[28px] font-bold tracking-tight text-[var(--text-1)]">{title}</h1>
        {description && (
          <p className="text-[14px] text-[var(--text-3)] mt-1.5">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
