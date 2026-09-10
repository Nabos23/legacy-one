'use client'

import * as React from 'react'
import { Select as SelectPrimitive } from '@base-ui/react/select'
import { Check, ChevronDown, Search } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SelectOption {
  value: string
  label: React.ReactNode
  disabled?: boolean
}

interface SelectProps {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  className?: string
  name?: string
  required?: boolean
  searchable?: boolean
  searchPlaceholder?: string
}

/** Styled dropdown built on @base-ui/react/select — drop-in replacement for a native `<select>`. */
export function Select({
  value,
  onValueChange,
  options,
  placeholder = 'Select…',
  disabled,
  className,
  name,
  required,
  searchable = false,
  searchPlaceholder = 'Search…',
}: SelectProps) {
  const [search, setSearch] = React.useState('')
  const searchInputRef = React.useRef<HTMLInputElement>(null)

  const filteredOptions = React.useMemo(() => {
    if (!searchable || !search.trim()) return options
    const query = search.toLowerCase()
    return options.filter((opt) => {
      const labelText = typeof opt.label === 'string' ? opt.label : String(opt.value)
      return labelText.toLowerCase().includes(query)
    })
  }, [options, searchable, search])

  return (
    <SelectPrimitive.Root
      items={filteredOptions}
      value={value}
      onValueChange={(v) => onValueChange(v as string)}
      disabled={disabled}
      name={name}
      required={required}
      onOpenChange={(open) => {
        if (!open) setSearch('')
        else if (searchable) {
          setTimeout(() => searchInputRef.current?.focus(), 50)
        }
      }}
    >
      <SelectPrimitive.Trigger
        className={cn(
          'flex h-9 w-full items-center justify-between gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-4 text-[13.5px] text-[var(--text-1)]',
          'transition-colors outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20 dark:focus:border-violet-500',
          'data-[popup-open]:border-violet-400 data-[popup-open]:ring-2 data-[popup-open]:ring-violet-500/20',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} className="truncate text-left" />
        <SelectPrimitive.Icon className="shrink-0 text-[var(--text-3)]">
          <ChevronDown size={14} />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Positioner sideOffset={6} className="z-50 outline-none">
          <SelectPrimitive.Popup
            className={cn(
              'animate-scaleIn glass-card max-h-72 min-w-[var(--anchor-width)] overflow-hidden rounded-2xl border border-border bg-card/95 p-1.5 backdrop-blur-2xl backdrop-saturate-150 outline-none shadow-2xl flex flex-col',
            )}
            style={{ transformOrigin: 'var(--transform-origin)' }}
          >
            {searchable && (
              <div className="p-1 pb-1.5 border-b border-border/50 shrink-0">
                <div className="relative flex items-center">
                  <Search size={14} className="absolute left-3 text-muted-foreground pointer-events-none" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => e.stopPropagation()}
                    placeholder={searchPlaceholder}
                    className="w-full h-8 pl-8 pr-3 text-xs bg-muted/50 border border-border/40 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30"
                  />
                </div>
              </div>
            )}
            <div className="overflow-y-auto max-h-60 p-0.5 space-y-0.5 scrollbar-none">
              {filteredOptions.length === 0 ? (
                <div className="py-3 px-2 text-center text-xs text-muted-foreground">
                  No matches found
                </div>
              ) : (
                filteredOptions.map((opt) => (
                  <SelectPrimitive.Item
                    key={opt.value}
                    value={opt.value}
                    disabled={opt.disabled}
                    className={cn(
                      'flex cursor-pointer items-center justify-between gap-2 rounded-xl px-3 py-2 text-[13.5px] text-foreground outline-none select-none',
                      'data-[highlighted]:bg-violet-500/10 data-[highlighted]:text-violet-600 dark:data-[highlighted]:text-violet-300 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50',
                    )}
                  >
                    <SelectPrimitive.ItemText>{opt.label}</SelectPrimitive.ItemText>
                    <SelectPrimitive.ItemIndicator>
                      <Check size={14} className="text-violet-500" />
                    </SelectPrimitive.ItemIndicator>
                  </SelectPrimitive.Item>
                ))
              )}
            </div>
          </SelectPrimitive.Popup>
        </SelectPrimitive.Positioner>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}
