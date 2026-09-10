'use client'

import { Input } from '@/components/ui/input'
import { isValidWidgetHexColor } from '@/lib/widget-styles'

interface ColorFieldProps {
  label: string
  /** Current hex value; empty/null/undefined means "auto / fall back". */
  value: string | null | undefined
  /** Receives the trimmed hex string, or '' when the field is cleared. */
  onChange: (value: string) => void
  /** Placeholder shown when the field is clearable, e.g. "Auto" or
   * "Falls back to theme color". */
  placeholder?: string
  /** Color painted on the swatch while the field itself is empty. */
  fallbackColor?: string
  /** Secondary label styling used inside dense grids. */
  subtle?: boolean
}

/** Expand #RGB to #RRGGBB and strip alpha so `<input type="color">` (which
 * only accepts #RRGGBB) can render the swatch. */
function toSwatchHex(value: string): string | null {
  const hex = value.trim().replace(/^#/, '')
  if (/^[0-9a-fA-F]{3}$/.test(hex)) return `#${hex[0]}${hex[0]}${hex[1]}${hex[1]}${hex[2]}${hex[2]}`
  if (/^[0-9a-fA-F]{6}$/.test(hex)) return `#${hex}`
  if (/^[0-9a-fA-F]{8}$/.test(hex)) return `#${hex.slice(0, 6)}`
  return null
}

/** Shared color control: native color swatch + hex text input + inline
 * invalid-hex error. Accepts #RGB / #RRGGBB / #RRGGBBAA (same rule the
 * backend enforces); empty means "auto" for clearable fields. */
export function ColorField({ label, value, onChange, placeholder, fallbackColor = '#4F46E5', subtle }: ColorFieldProps) {
  const current = value ?? ''
  const invalid = !isValidWidgetHexColor(current)
  const swatch = toSwatchHex(current) ?? toSwatchHex(fallbackColor) ?? '#4F46E5'

  return (
    <div>
      {subtle ? (
        <label className="text-[12px] text-[var(--text-3)] block mb-1.5">{label}</label>
      ) : (
        <label className="text-[13px] font-medium block mb-2">{label}</label>
      )}
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={swatch}
          onChange={e => onChange(e.target.value)}
          aria-label={`${label} swatch`}
          className="w-10 h-10 shrink-0 rounded-lg border border-[var(--border)] cursor-pointer bg-transparent"
        />
        <Input
          value={current}
          onChange={e => onChange(e.target.value.trim())}
          placeholder={placeholder ?? '#4F46E5'}
          aria-invalid={invalid || undefined}
          className={invalid ? 'border-red-400 focus:border-red-400 focus:ring-red-500/20' : undefined}
        />
      </div>
      {invalid && (
        <p className="text-[11px] text-red-500 dark:text-red-400 mt-1">
          Enter a hex color like #4F46E5 (or #RGB / #RRGGBBAA), or leave empty.
        </p>
      )}
    </div>
  )
}
