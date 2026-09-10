import * as React from 'react'
import { cn } from '@/lib/utils'

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: React.ReactNode
  rightElement?: React.ReactNode
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, leftIcon, rightElement, ...props }, ref) => (
    <div className="relative w-full">
      {leftIcon && (
        <div className="absolute left-3.5 top-1/2 transform -translate-y-1/2 text-[var(--text-3)] pointer-events-none">
          {leftIcon}
        </div>
      )}
      <input
        type={type}
        className={cn(
          'flex h-9 w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13.5px] text-[var(--text-1)] placeholder:text-[var(--text-3)] transition-colors focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 focus:ring-offset-0 disabled:cursor-not-allowed disabled:opacity-50',
          leftIcon ? 'pl-10' : '',
          rightElement ? 'pr-10' : '',
          className
        )}
        ref={ref}
        {...props}
      />
      {rightElement && (
        <div className="absolute right-3.5 top-1/2 transform -translate-y-1/2 text-[var(--text-3)] flex items-center justify-center">
          {rightElement}
        </div>
      )}
    </div>
  )
)
Input.displayName = 'Input'

export { Input }
