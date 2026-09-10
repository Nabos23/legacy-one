import { cn } from '@/lib/utils'

interface FormFieldProps {
  label?: string
  htmlFor?: string
  hint?: string
  error?: string
  required?: boolean
  className?: string
  children: React.ReactNode
}

/** Label + control + hint/error wrapper for consistent form layout. */
export function FormField({ label, htmlFor, hint, error, required, className, children }: FormFieldProps) {
  return (
    <div className={cn('space-y-2', className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-[13px] font-medium block text-[var(--text-2)]">
          {label}
          {required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-[12px] text-red-500 dark:text-red-400">{error}</p>
      ) : hint ? (
        <p className="text-[12px] text-[var(--text-3)]">{hint}</p>
      ) : null}
    </div>
  )
}
