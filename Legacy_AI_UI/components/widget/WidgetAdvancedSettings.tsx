'use client'

import { useState } from 'react'
import { Loader2, Plus, RotateCcw, Send, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { InfoBox } from '@/components/ui/info-box'
import { ImageUploadField } from '@/components/widget/ImageUploadField'
import { widgetsApi } from '@/lib/api/widgets'
import { useToast } from '@/hooks/use-toast'
import type {
  DayKey,
  LeadField,
  LeadFieldType,
  WidgetAccessibilityInput,
  WidgetAvailabilityInput,
  WidgetBehaviorInput,
  WidgetLayoutInput,
  WidgetPosition,
  WidgetTriggersInput,
  WidgetWebhooksInput,
  WidgetWebhookDeliveryItem,
} from '@/types'

export interface WidgetAdvancedValue {
  triggers: WidgetTriggersInput
  behavior: WidgetBehaviorInput
  availability: WidgetAvailabilityInput
  accessibility: WidgetAccessibilityInput
  layout: WidgetLayoutInput
  leadFields: LeadField[]
  webhooks: WidgetWebhooksInput
}

/** Every section below shares this contract -- each only reads/writes its
 * own slice, but takes the whole value so callers don't need per-section
 * prop types. One section per settings tab (see WidgetDetailView/CreateForm). */
export interface WidgetAdvancedSectionProps {
  value: WidgetAdvancedValue
  onChange: (next: WidgetAdvancedValue) => void
  /** Only set by WidgetDetailView (a saved widget has an id) -- LayoutSection
   * uses it to offer a real image upload for the custom launcher icon;
   * WidgetCreateForm omits it, so that field falls back to a plain URL input. */
  widgetId?: string
}

const DAYS: { key: DayKey; label: string }[] = [
  { key: 'mon', label: 'Mon' },
  { key: 'tue', label: 'Tue' },
  { key: 'wed', label: 'Wed' },
  { key: 'thu', label: 'Thu' },
  { key: 'fri', label: 'Fri' },
  { key: 'sat', label: 'Sat' },
  { key: 'sun', label: 'Sun' },
]

const LANGUAGE_OPTIONS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'hi', label: 'Hindi' },
  { value: 'ar', label: 'Arabic' },
]

const LEAD_FIELD_TYPE_OPTIONS: { value: LeadFieldType; label: string }[] = [
  { value: 'text', label: 'Text' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
]

function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="w-4 h-4 accent-violet-600"
      />
      <span className="text-[13px]">{label}</span>
    </label>
  )
}

function useSectionSetter({ value, onChange }: WidgetAdvancedSectionProps) {
  return <K extends keyof WidgetAdvancedValue>(key: K, patch: Partial<WidgetAdvancedValue[K]>) => {
    onChange({ ...value, [key]: { ...(value[key] as object), ...patch } })
  }
}

export function TriggersSection({ value, onChange }: WidgetAdvancedSectionProps) {
  const set = useSectionSetter({ value, onChange })
  const [greetingPath, setGreetingPath] = useState('')
  const [greetingText, setGreetingText] = useState('')

  const addTargetedGreeting = () => {
    if (!greetingPath.trim() || !greetingText.trim()) return
    const next = [...(value.triggers.targeted_greetings ?? []), { path_pattern: greetingPath.trim(), greeting: greetingText.trim() }]
    set('triggers', { targeted_greetings: next })
    setGreetingPath('')
    setGreetingText('')
  }

  const removeTargetedGreeting = (index: number) => {
    const next = (value.triggers.targeted_greetings ?? []).filter((_, i) => i !== index)
    set('triggers', { targeted_greetings: next })
  }

  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
      <Checkbox
        checked={!!value.triggers.auto_open}
        onChange={v => set('triggers', { auto_open: v })}
        label="Automatically open the widget after a delay"
      />
      {value.triggers.auto_open && (
        <div className="pl-6 max-w-[220px]">
          <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Delay (ms)</label>
          <Input
            type="number"
            value={value.triggers.auto_open_delay_ms ?? 4000}
            onChange={e => set('triggers', { auto_open_delay_ms: Number(e.target.value) })}
          />
        </div>
      )}
      <Checkbox
        checked={value.triggers.open_on_scroll_percent != null}
        onChange={v => set('triggers', { open_on_scroll_percent: v ? 50 : null })}
        label="Open when the visitor scrolls past a percentage of the page"
      />
      {value.triggers.open_on_scroll_percent != null && (
        <div className="pl-6 max-w-[220px]">
          <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Scroll percent</label>
          <Input
            type="number"
            min={0}
            max={100}
            value={value.triggers.open_on_scroll_percent}
            onChange={e => set('triggers', { open_on_scroll_percent: Number(e.target.value) })}
          />
        </div>
      )}

      <div>
        <label className="text-[13px] font-medium block mb-2">Targeted greetings by page path</label>
        <p className="text-[11px] text-[var(--text-3)] mb-2">
          Overrides the default greeting when the host page&apos;s path matches (supports a trailing <code>*</code> wildcard, e.g. <code>/pricing*</code>).
        </p>
        <div className="flex gap-2 mb-2">
          <Input value={greetingPath} onChange={e => setGreetingPath(e.target.value)} placeholder="/pricing*" className="w-[160px]" />
          <Input value={greetingText} onChange={e => setGreetingText(e.target.value)} placeholder="Questions about pricing?" className="flex-1" />
          <Button variant="outline" onClick={addTargetedGreeting}>Add</Button>
        </div>
        {(value.triggers.targeted_greetings ?? []).length === 0 && !greetingPath && !greetingText && (
          <button
            type="button"
            onClick={() => { setGreetingPath('/pricing*'); setGreetingText('Questions about pricing? I can help you compare plans.') }}
            className="text-[11.5px] text-violet-600 dark:text-violet-400 hover:underline"
          >
            Try an example: greet pricing-page visitors differently
          </button>
        )}
        {(value.triggers.targeted_greetings ?? []).map((g, i) => (
          <div key={i} className="flex items-center gap-2 text-[12px] py-1">
            <code className="text-violet-600 dark:text-violet-400">{g.path_pattern}</code>
            <span className="text-[var(--text-3)] truncate flex-1">{g.greeting}</span>
            <button onClick={() => removeTargetedGreeting(i)}><X className="w-3.5 h-3.5 text-[var(--text-3)]" /></button>
          </div>
        ))}
      </div>
    </div>
  )
}

export function BehaviorSection({ value, onChange }: WidgetAdvancedSectionProps) {
  const set = useSectionSetter({ value, onChange })
  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
      <div className="max-w-[220px]">
        <label className="text-[13px] font-medium block mb-2">Response language</label>
        <Select
          value={value.behavior.response_language ?? 'auto'}
          onValueChange={v => set('behavior', { response_language: v })}
          options={LANGUAGE_OPTIONS}
        />
      </div>
      <div>
        <label className="text-[13px] font-medium block mb-2">Tone overlay (optional)</label>
        <p className="text-[11px] text-[var(--text-3)] mb-2">
          Layered on top of the source agent&apos;s own prompt — never replaces it.
        </p>
        <Textarea
          value={value.behavior.tone_instructions ?? ''}
          onChange={e => set('behavior', { tone_instructions: e.target.value })}
          placeholder="Be warm and concise. Avoid jargon."
        />
      </div>
      <Checkbox
        checked={!!value.behavior.welcome_sound}
        onChange={v => set('behavior', { welcome_sound: v })}
        label="Play a sound when a new message arrives"
      />
      <div>
        <Checkbox
          checked={!!value.behavior.allow_attachments}
          onChange={v => set('behavior', { allow_attachments: v })}
          label="Allow visitors to attach files"
        />
        <p className="text-[11px] text-[var(--text-3)] mt-1 pl-6">
          Visitors can attach images, PDFs, and text files (up to 10 MB each) to their messages.
        </p>
      </div>
      <div>
        <Checkbox
          checked={!!value.behavior.rich_messages}
          onChange={v => set('behavior', { rich_messages: v })}
          label="Let the agent send buttons and cards"
        />
        <p className="text-[11px] text-[var(--text-3)] mt-1 pl-6">
          Teaches the agent it can reply with tappable choice buttons and rich cards (title, image, link,
          call-to-action) where they help — e.g. offering next steps or showcasing plans. The agent decides
          when to use them.
        </p>
      </div>
    </div>
  )
}

export function AvailabilitySection({ value, onChange }: WidgetAdvancedSectionProps) {
  const set = useSectionSetter({ value, onChange })
  const updateDaySchedule = (day: DayKey, patch: Partial<{ enabled: boolean; start: string; end: string }>) => {
    set('availability', {
      schedule: { ...(value.availability.schedule ?? {}), [day]: { ...(value.availability.schedule?.[day] ?? {}), ...patch } },
    })
  }

  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
      <Checkbox
        checked={!!value.availability.enabled}
        onChange={v => set('availability', { enabled: v })}
        label="Restrict live chat to business hours"
      />
      {value.availability.enabled && (
        <div className="pl-6 space-y-3">
          <div className="max-w-[260px]">
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Timezone (IANA, e.g. America/New_York)</label>
            <Input value={value.availability.timezone ?? 'UTC'} onChange={e => set('availability', { timezone: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            {DAYS.map(({ key, label }) => {
              const day = value.availability.schedule?.[key]
              return (
                <div key={key} className="flex items-center gap-3">
                  <label className="flex items-center gap-2 w-16 shrink-0">
                    <input
                      type="checkbox"
                      checked={!!day?.enabled}
                      onChange={e => updateDaySchedule(key, { enabled: e.target.checked })}
                      className="w-3.5 h-3.5 accent-violet-600"
                    />
                    <span className="text-[12px]">{label}</span>
                  </label>
                  <Input
                    type="time"
                    value={day?.start ?? '09:00'}
                    onChange={e => updateDaySchedule(key, { start: e.target.value })}
                    disabled={!day?.enabled}
                    className="w-[110px]"
                  />
                  <span className="text-[12px] text-[var(--text-3)]">to</span>
                  <Input
                    type="time"
                    value={day?.end ?? '17:00'}
                    onChange={e => updateDaySchedule(key, { end: e.target.value })}
                    disabled={!day?.enabled}
                    className="w-[110px]"
                  />
                </div>
              )
            })}
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Offline message</label>
            <Input
              value={value.availability.offline_message ?? ''}
              onChange={e => set('availability', { offline_message: e.target.value })}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export function AccessibilitySection({ value, onChange }: WidgetAdvancedSectionProps) {
  const set = useSectionSetter({ value, onChange })
  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-3">
      <Checkbox checked={!!value.accessibility.reduced_motion} onChange={v => set('accessibility', { reduced_motion: v })} label="Reduced motion" />
      <Checkbox checked={!!value.accessibility.high_contrast} onChange={v => set('accessibility', { high_contrast: v })} label="High contrast" />
      <Checkbox checked={!!value.accessibility.large_text} onChange={v => set('accessibility', { large_text: v })} label="Larger text" />
    </div>
  )
}

const LAUNCHER_SHAPE_OPTIONS = [
  { value: 'circle', label: 'Circle' },
  { value: 'rounded-square', label: 'Rounded square' },
]

const LAUNCHER_ICON_OPTIONS = [
  { value: 'chat', label: 'Chat bubble' },
  { value: 'message', label: 'Message' },
  { value: 'robot', label: 'Robot' },
  { value: 'custom', label: 'Custom image URL' },
]

const LAUNCHER_HOVER_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'scale', label: 'Scale up' },
  { value: 'shadow', label: 'Shadow lift' },
  { value: 'both', label: 'Scale + shadow' },
]

const SHADOW_STYLE_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'soft', label: 'Soft' },
  { value: 'medium', label: 'Medium' },
  { value: 'strong', label: 'Strong' },
]

const BUBBLE_STYLE_OPTIONS = [
  { value: 'rounded', label: 'Rounded' },
  { value: 'square', label: 'Square' },
  { value: 'soft', label: 'Soft (subtle radius)' },
]

const SEND_BUTTON_SHAPE_OPTIONS = [
  { value: 'circle', label: 'Circle' },
  { value: 'rounded', label: 'Rounded' },
  { value: 'square', label: 'Square' },
]

const SPACING_DENSITY_OPTIONS = [
  { value: 'compact', label: 'Compact' },
  { value: 'comfortable', label: 'Comfortable' },
  { value: 'spacious', label: 'Spacious' },
]

const ANIMATION_STYLE_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'fade', label: 'Fade' },
  { value: 'slide', label: 'Slide up' },
  { value: 'scale', label: 'Scale in' },
]

/** Server-enforced bounds (backend/widget/schemas.py) mirrored client-side
 * so admins see the problem before a rejected save. */
const LAYOUT_BOUNDS = {
  widget_min_width: { min: 200, max: 800, label: 'Min width' },
  widget_min_height: { min: 200, max: 900, label: 'Min height' },
  widget_max_width: { min: 240, max: 1200, label: 'Max width' },
  widget_max_height: { min: 300, max: 1400, label: 'Max height' },
  mobile_breakpoint_px: { min: 320, max: 1280, label: 'Mobile breakpoint' },
} as const

function layoutIssues(layout: WidgetLayoutInput): string[] {
  const issues: string[] = []
  for (const [key, bound] of Object.entries(LAYOUT_BOUNDS)) {
    const v = layout[key as keyof WidgetLayoutInput] as number | undefined
    if (v != null && (v < bound.min || v > bound.max)) {
      issues.push(`${bound.label} must be between ${bound.min} and ${bound.max}px.`)
    }
  }
  const { widget_width, widget_height, widget_min_width, widget_min_height, widget_max_width, widget_max_height } = layout
  if (widget_min_width != null && widget_width != null && widget_min_width > widget_width) {
    issues.push('Min width can’t exceed the base width.')
  }
  if (widget_width != null && widget_max_width != null && widget_width > widget_max_width) {
    issues.push('Width can’t exceed the max width.')
  }
  if (widget_min_height != null && widget_height != null && widget_min_height > widget_height) {
    issues.push('Min height can’t exceed the base height.')
  }
  if (widget_height != null && widget_max_height != null && widget_height > widget_max_height) {
    issues.push('Height can’t exceed the max height.')
  }
  return issues
}

const POSITION_OPTIONS: { value: WidgetPosition; label: string }[] = [
  { value: 'bottom-left', label: 'Bottom left' },
  { value: 'bottom-right', label: 'Bottom right' },
]

export interface LauncherSectionProps extends WidgetAdvancedSectionProps {
  /** branding.position lives on the branding object, not layout -- the
   * callers pass it in separately so the Launcher tab is its one home. */
  position?: WidgetPosition
  onPositionChange?: (position: WidgetPosition) => void
}

/** Launcher tab: everything about the floating button itself, split out of
 * the Layout tab (which keeps the chat window's dimensions/shape/animation). */
export function LauncherSection({ value, onChange, widgetId, position, onPositionChange }: LauncherSectionProps) {
  const set = useSectionSetter({ value, onChange })
  const layout = value.layout

  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-6">
      {onPositionChange && (
        <div>
          <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Position</p>
          <div className="grid grid-cols-2 gap-3 max-w-[360px]">
            {POSITION_OPTIONS.map(opt => {
              const active = (position ?? 'bottom-right') === opt.value
              const left = opt.value === 'bottom-left'
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => onPositionChange(opt.value)}
                  className={`p-3 rounded-[var(--radius-lg)] border transition-colors text-left ${
                    active ? 'border-violet-500 bg-violet-500/10' : 'border-[var(--border)] hover:border-violet-300'
                  }`}
                >
                  <div className="relative h-12 rounded-md border border-dashed border-[var(--border)] bg-[var(--surface-2)] mb-2">
                    <span
                      className={`absolute bottom-1.5 w-3 h-3 rounded-full ${active ? 'bg-violet-500' : 'bg-[var(--text-3)]'} ${left ? 'left-1.5' : 'right-1.5'}`}
                    />
                  </div>
                  <p className="text-[12.5px] font-medium">{opt.label}</p>
                </button>
              )
            })}
          </div>
        </div>
      )}

      <div className={onPositionChange ? 'pt-4 border-t border-[var(--border)]' : ''}>
        <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Launcher button</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Size (px)</label>
            <Input type="number" value={layout.launcher_size ?? 56} onChange={e => set('layout', { launcher_size: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Shape</label>
            <Select value={layout.launcher_shape ?? 'circle'} onValueChange={v => set('layout', { launcher_shape: v as typeof layout.launcher_shape })} options={LAUNCHER_SHAPE_OPTIONS} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Icon</label>
            <Select value={layout.launcher_icon ?? 'chat'} onValueChange={v => set('layout', { launcher_icon: v as typeof layout.launcher_icon })} options={LAUNCHER_ICON_OPTIONS} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Hover effect</label>
            <Select value={layout.launcher_hover_effect ?? 'scale'} onValueChange={v => set('layout', { launcher_hover_effect: v as typeof layout.launcher_hover_effect })} options={LAUNCHER_HOVER_OPTIONS} />
          </div>
          {layout.launcher_icon === 'custom' && (
            <div className="sm:col-span-2">
              {widgetId ? (
                <ImageUploadField
                  widgetId={widgetId}
                  label="Custom icon"
                  value={layout.launcher_icon_url}
                  onChange={url => set('layout', { launcher_icon_url: url })}
                />
              ) : (
                <>
                  <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Custom icon URL</label>
                  <Input value={layout.launcher_icon_url ?? ''} onChange={e => set('layout', { launcher_icon_url: e.target.value })} placeholder="https://your-site.com/icon.svg" />
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function LayoutSection({ value, onChange }: WidgetAdvancedSectionProps) {
  const set = useSectionSetter({ value, onChange })
  const layout = value.layout
  const issues = layoutIssues(layout)

  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-6">
      <div>
        <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Widget dimensions</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Width (px)</label>
            <Input type="number" value={layout.widget_width ?? 380} onChange={e => set('layout', { widget_width: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Height (px)</label>
            <Input type="number" value={layout.widget_height ?? 600} onChange={e => set('layout', { widget_height: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Min width (px)</label>
            <Input type="number" value={layout.widget_min_width ?? 300} onChange={e => set('layout', { widget_min_width: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Min height (px)</label>
            <Input type="number" value={layout.widget_min_height ?? 400} onChange={e => set('layout', { widget_min_height: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Max width (px)</label>
            <Input type="number" value={layout.widget_max_width ?? 480} onChange={e => set('layout', { widget_max_width: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Max height (px)</label>
            <Input type="number" value={layout.widget_max_height ?? 760} onChange={e => set('layout', { widget_max_height: Number(e.target.value) })} />
          </div>
        </div>
        {issues.length > 0 && (
          <ul className="mt-3 space-y-1">
            {issues.map(issue => (
              <li key={issue} className="text-[12px] text-red-500 dark:text-red-400">{issue}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="pt-4 border-t border-[var(--border)]">
        <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Positioning</p>
        <div className="grid grid-cols-2 gap-3 max-w-[320px]">
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Horizontal offset (px)</label>
            <Input type="number" value={layout.offset_x ?? 20} onChange={e => set('layout', { offset_x: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Vertical offset (px)</label>
            <Input type="number" value={layout.offset_y ?? 20} onChange={e => set('layout', { offset_y: Number(e.target.value) })} />
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-[var(--border)]">
        <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Shape, shadow & spacing</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Border radius (px)</label>
            <Input type="number" value={layout.border_radius ?? 16} onChange={e => set('layout', { border_radius: Number(e.target.value) })} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Shadow</label>
            <Select value={layout.shadow_style ?? 'medium'} onValueChange={v => set('layout', { shadow_style: v as typeof layout.shadow_style })} options={SHADOW_STYLE_OPTIONS} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Message bubble style</label>
            <Select value={layout.bubble_style ?? 'rounded'} onValueChange={v => set('layout', { bubble_style: v as typeof layout.bubble_style })} options={BUBBLE_STYLE_OPTIONS} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Send button shape</label>
            <Select value={layout.send_button_shape ?? 'circle'} onValueChange={v => set('layout', { send_button_shape: v as typeof layout.send_button_shape })} options={SEND_BUTTON_SHAPE_OPTIONS} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Spacing density</label>
            <Select value={layout.spacing_density ?? 'comfortable'} onValueChange={v => set('layout', { spacing_density: v as typeof layout.spacing_density })} options={SPACING_DENSITY_OPTIONS} />
          </div>
          <div>
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Open/close animation</label>
            <Select value={layout.animation_style ?? 'fade'} onValueChange={v => set('layout', { animation_style: v as typeof layout.animation_style })} options={ANIMATION_STYLE_OPTIONS} />
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-[var(--border)] space-y-3">
        <p className="text-[14px] font-semibold text-[var(--text-1)]">Mobile</p>
        <Checkbox
          checked={layout.mobile_full_screen !== false}
          onChange={v => set('layout', { mobile_full_screen: v })}
          label="Show full-screen on mobile devices"
        />
        {layout.mobile_full_screen !== false && (
          <div className="pl-6 max-w-[220px]">
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Breakpoint (px)</label>
            <Input type="number" value={layout.mobile_breakpoint_px ?? 640} onChange={e => set('layout', { mobile_breakpoint_px: Number(e.target.value) })} />
          </div>
        )}
      </div>
    </div>
  )
}

export function LeadCaptureSection({ value, onChange }: WidgetAdvancedSectionProps) {
  const [leadFieldName, setLeadFieldName] = useState('')
  const [leadFieldLabel, setLeadFieldLabel] = useState('')
  const [leadFieldType, setLeadFieldType] = useState<LeadFieldType>('text')

  const addLeadField = () => {
    if (!leadFieldName.trim() || !leadFieldLabel.trim()) return
    const next: LeadField[] = [
      ...value.leadFields,
      { field_name: leadFieldName.trim(), label: leadFieldLabel.trim(), field_type: leadFieldType, required: true },
    ]
    onChange({ ...value, leadFields: next })
    setLeadFieldName('')
    setLeadFieldLabel('')
    setLeadFieldType('text')
  }

  const removeLeadField = (index: number) => {
    onChange({ ...value, leadFields: value.leadFields.filter((_, i) => i !== index) })
  }

  const setLeadFieldRequired = (index: number, required: boolean) => {
    onChange({
      ...value,
      leadFields: value.leadFields.map((f, i) => (i === index ? { ...f, required } : f)),
    })
  }

  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
      <p className="text-[12px] text-[var(--text-3)]">
        If any fields are added, visitors fill this out before their first message.
      </p>
      <div className="flex gap-2">
        <Input value={leadFieldName} onChange={e => setLeadFieldName(e.target.value)} placeholder="field_name" className="w-[130px]" />
        <Input value={leadFieldLabel} onChange={e => setLeadFieldLabel(e.target.value)} placeholder="Label shown to visitor" className="flex-1" />
        <Select value={leadFieldType} onValueChange={v => setLeadFieldType(v as LeadFieldType)} options={LEAD_FIELD_TYPE_OPTIONS} className="w-[110px]" />
        <Button variant="outline" onClick={addLeadField}><Plus className="w-3.5 h-3.5" /></Button>
      </div>
      {value.leadFields.length === 0 && (
        <button
          type="button"
          onClick={() =>
            onChange({
              ...value,
              leadFields: [
                { field_name: 'name', label: 'Your name', field_type: 'text', required: true },
                { field_name: 'email', label: 'Work email', field_type: 'email', required: true },
              ],
            })
          }
          className="text-[11.5px] text-violet-600 dark:text-violet-400 hover:underline"
        >
          Start with the classic setup: Name + Email
        </button>
      )}
      {value.leadFields.map((f, i) => (
        <div key={i} className="flex items-center gap-2 text-[12px] py-1">
          <code className="text-violet-600 dark:text-violet-400">{f.field_name}</code>
          <span className="text-[var(--text-3)] flex-1">{f.label} ({f.field_type})</span>
          <label className="flex items-center gap-1.5 cursor-pointer shrink-0" title="Visitors must fill this field before chatting">
            <input
              type="checkbox"
              checked={f.required}
              onChange={e => setLeadFieldRequired(i, e.target.checked)}
              className="w-3.5 h-3.5 accent-violet-600"
            />
            <span className="text-[11.5px] text-[var(--text-3)]">Required</span>
          </label>
          <button onClick={() => removeLeadField(i)}><X className="w-3.5 h-3.5 text-[var(--text-3)]" /></button>
        </div>
      ))}
    </div>
  )
}

const WEBHOOK_EVENTS: { key: 'conversation_started' | 'lead_captured' | 'message_sent' | 'feedback_submitted'; label: string }[] = [
  { key: 'conversation_started', label: 'On conversation started' },
  { key: 'lead_captured', label: 'On lead captured' },
  { key: 'message_sent', label: 'On visitor message sent' },
  { key: 'feedback_submitted', label: 'On feedback (👍/👎) submitted' },
]

function WebhookDeliveryLog({ widgetId }: { widgetId: string }) {
  const { toast } = useToast()
  const [deliveries, setDeliveries] = useState<WidgetWebhookDeliveryItem[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [replayingId, setReplayingId] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await widgetsApi.getWebhookDeliveries(widgetId, 1, 20)
      setDeliveries(res.items)
    } catch {
      setDeliveries([])
    } finally {
      setLoading(false)
    }
  }

  const handleReplay = async (delivery: WidgetWebhookDeliveryItem) => {
    setReplayingId(delivery.id)
    try {
      const res = await widgetsApi.replayWebhookDelivery(widgetId, delivery.id)
      if (res.ok) toast.success(`Replayed — HTTP ${res.status_code}`)
      else toast.error(res.error ? `Replay failed: ${res.error}` : `Endpoint answered HTTP ${res.status_code}`)
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Replay failed')
    } finally {
      setReplayingId(null)
    }
  }

  return (
    <div className="pt-3 border-t border-[var(--border)]">
      <div className="flex items-center justify-between">
        <p className="text-[12px] font-medium">Recent deliveries</p>
        <Button variant="ghost" size="xs" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : deliveries === null ? 'Load' : 'Refresh'}
        </Button>
      </div>
      {deliveries !== null && (
        deliveries.length === 0 ? (
          <p className="text-[12px] text-[var(--text-3)] mt-2">No deliveries recorded in the last 30 days.</p>
        ) : (
          <div className="mt-2 space-y-1.5 max-h-64 overflow-y-auto">
            {deliveries.map(d => (
              <div key={d.id} className="flex items-center gap-2 text-[11.5px] px-2.5 py-1.5 rounded-lg border border-[var(--border)]">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${d.ok ? 'bg-emerald-500' : 'bg-red-500'}`} />
                <span className="font-medium shrink-0">{d.event}</span>
                {d.kind && d.kind !== 'event' && (
                  <span className="shrink-0 rounded px-1 py-px text-[10px] uppercase tracking-wide bg-[var(--surface-2)] text-[var(--text-3)] border border-[var(--border)]">{d.kind}</span>
                )}
                <span className="text-[var(--text-3)] truncate flex-1">{d.url}</span>
                <span className="text-[var(--text-3)] shrink-0">
                  {d.status_code ? `HTTP ${d.status_code}` : d.ok ? 'ok' : 'failed'}
                  {d.attempts > 1 ? ` · ${d.attempts} tries` : ''}
                </span>
                <span className="text-[var(--text-3)] shrink-0">{new Date(d.created_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}</span>
                {!d.ok && d.can_replay && (
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => handleReplay(d)}
                    disabled={replayingId !== null}
                    title="Re-deliver this payload to the event's current URL"
                  >
                    {replayingId === d.id ? <Loader2 className="w-3 h-3" /> : <RotateCcw className="w-3 h-3" />}
                  </Button>
                )}
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}

export function WebhooksSection({ value, onChange, widgetId }: WidgetAdvancedSectionProps) {
  const { toast } = useToast()
  const [testingEvent, setTestingEvent] = useState<string | null>(null)

  // Fires against the SAVED config (URL/secret on the server), so unsaved
  // edits in the fields above don't participate -- the button says so.
  const handleTestFire = async (event: string) => {
    if (!widgetId) return
    setTestingEvent(event)
    try {
      const res = await widgetsApi.testWebhook(widgetId, event)
      if (res.ok) toast.success(`Delivered — HTTP ${res.status_code}`)
      else toast.error(res.error ? `Failed: ${res.error}` : `Endpoint answered HTTP ${res.status_code}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Test delivery failed')
    } finally {
      setTestingEvent(null)
    }
  }

  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-5">
      <p className="text-[12px] text-[var(--text-3)]">
        Outbound POST when an event fires (retried up to 3 times on transient failures). Payloads are HMAC-signed (header <code>X-OneAI-Signature</code>) if a secret is set.
      </p>
      {WEBHOOK_EVENTS.map(({ key: event, label }) => {
        const target = value.webhooks[event] ?? {}
        return (
          <div key={event} className="space-y-2 pt-2 border-t border-[var(--border)] first:border-t-0 first:pt-0">
            <div className="flex items-center justify-between">
              <p className="text-[12px] font-medium">{label}</p>
              {widgetId && (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => handleTestFire(event)}
                  disabled={testingEvent !== null || !target.url}
                  title="Send a sample payload to the saved URL for this event"
                >
                  {testingEvent === event ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Send className="w-3.5 h-3.5 mr-1.5" />}
                  Send test
                </Button>
              )}
            </div>
            <Input
              value={target.url ?? ''}
              onChange={e =>
                onChange({ ...value, webhooks: { ...value.webhooks, [event]: { ...target, url: e.target.value } } })
              }
              placeholder="https://your-system.com/webhook"
            />
            <div className="flex items-center gap-3">
              <Input
                type="password"
                value={target.secret ?? ''}
                onChange={e =>
                  onChange({ ...value, webhooks: { ...value.webhooks, [event]: { ...target, secret: e.target.value } } })
                }
                placeholder="Signing secret (leave blank to keep existing)"
                className="flex-1"
              />
              <Checkbox
                checked={target.is_active !== false}
                onChange={v => onChange({ ...value, webhooks: { ...value.webhooks, [event]: { ...target, is_active: v } } })}
                label="Active"
              />
            </div>
          </div>
        )
      })}
      <InfoBox variant="info">
        A previously-saved secret is never shown here — leave the field blank to keep it, or type a new value to replace it.
      </InfoBox>
      {widgetId && <WebhookDeliveryLog widgetId={widgetId} />}
    </div>
  )
}
