'use client'

import { Check } from 'lucide-react'
import { WIDGET_THEME_PRESETS } from '@/lib/widget-styles'
import type { WidgetBrandingInput } from '@/types'

interface ThemePresetPickerProps {
  current: WidgetBrandingInput
  onApply: (preset: WidgetBrandingInput) => void
}

/** Curated color/typography combos -- a one-click starting point instead of
 * setting seven color fields by hand. Each preset renders as a mini widget
 * thumbnail (header bar + bubbles in its palette) so admins pick by look,
 * not by name. Applying only touches color/dark-mode fields; copy, layout,
 * and images are left alone. */
export function ThemePresetPicker({ current, onApply }: ThemePresetPickerProps) {
  return (
    <div>
      <label className="text-[13px] font-medium block mb-2">Theme presets</label>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {WIDGET_THEME_PRESETS.map(preset => {
          const isActive = current.theme_color === preset.branding.theme_color && current.dark_mode === preset.branding.dark_mode
          const dark = !!preset.branding.dark_mode
          const surfaceBg = dark ? '#111827' : '#ffffff'
          const assistantBubble = dark ? '#1f2937' : '#f3f4f6'
          return (
            <button
              key={preset.key}
              type="button"
              onClick={() => onApply(preset.branding)}
              title={`Apply the ${preset.label} theme`}
              className={`group text-left rounded-lg border overflow-hidden transition-all ${
                isActive
                  ? 'border-violet-500 ring-2 ring-violet-500/30'
                  : 'border-[var(--border)] hover:border-violet-300 hover:shadow-sm'
              }`}
            >
              {/* Mini widget: header bar + one assistant + one visitor bubble */}
              <div className="h-[52px] flex flex-col" style={{ backgroundColor: surfaceBg }}>
                <div className="h-[14px] shrink-0" style={{ backgroundColor: preset.swatch[0] }} />
                <div className="flex-1 px-1.5 py-1 space-y-1">
                  <div className="h-[7px] w-3/5 rounded-full" style={{ backgroundColor: assistantBubble }} />
                  <div className="h-[7px] w-2/5 rounded-full ml-auto" style={{ backgroundColor: preset.swatch[0] }} />
                </div>
              </div>
              <div className="flex items-center justify-between px-1.5 py-1 border-t border-[var(--border)] bg-[var(--surface)]">
                <span className="text-[10.5px] font-medium truncate">{preset.label}</span>
                {isActive && <Check className="w-3 h-3 shrink-0 text-violet-600 dark:text-violet-400" />}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
