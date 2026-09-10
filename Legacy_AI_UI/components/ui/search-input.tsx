'use client'

import { useState } from 'react'
import { Search, X } from 'lucide-react'
import { Input, type InputProps } from './input'
import { cn } from '@/lib/utils'

export interface SearchInputProps extends Omit<InputProps, 'leftIcon' | 'type'> {}

/** The standard search bar component used across the application — renders a rounded pill input
 * with left search icon and a clear button whenever a value is present. */
export function SearchInput({ className, style, value, onChange, onFocus, onBlur, rightElement, placeholder = 'Search...', ...props }: SearchInputProps) {
  const [focused, setFocused] = useState(false)
  const hasValue = typeof value === 'string' && value.length > 0

  const clear = () => {
    onChange?.({ target: { value: '' } } as React.ChangeEvent<HTMLInputElement>)
  }

  return (
    <div
      className={cn(
        'relative w-full shrink-0 transition-all duration-200',
        className,
      )}
      style={{ borderRadius: 9999 }}
    >
      <Input
        type="text"
        value={value}
        onChange={onChange}
        onFocus={e => { setFocused(true); onFocus?.(e) }}
        onBlur={e => { setFocused(false); onBlur?.(e) }}
        placeholder={placeholder}
        leftIcon={<Search className="w-4 h-4 text-[var(--text-3)]" />}
        rightElement={rightElement ?? (hasValue ? (
          <button
            type="button"
            onClick={clear}
            aria-label="Clear search"
            className="text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors p-1 rounded-full hover:bg-black/5 dark:hover:bg-white/10"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        ) : undefined)}
        className="w-full"
        style={{ ...style, borderRadius: 9999 }}
        {...props}
      />
    </div>
  )
}
