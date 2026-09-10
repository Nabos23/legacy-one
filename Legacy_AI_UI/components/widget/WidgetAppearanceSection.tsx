'use client'

import { useState } from 'react'
import { ChevronDown, Loader2, Wand2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { extractBrandColors } from '@/lib/brand-colors'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { ColorField } from '@/components/widget/ColorField'
import { ImageUploadField } from '@/components/widget/ImageUploadField'
import { ThemePresetPicker } from '@/components/widget/ThemePresetPicker'
import { WIDGET_CUSTOM_FONT_VALUE, WIDGET_FONT_STACKS } from '@/lib/widget-styles'
import type { WidgetBrandingInput, WidgetLocaleCopy, WidgetTextDirection } from '@/types'

const CUSTOM_CSS_MAX = 20_000

const TEXT_DIRECTION_OPTIONS: { value: WidgetTextDirection; label: string }[] = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'ltr', label: 'Left-to-right' },
  { value: 'rtl', label: 'Right-to-left' },
]

const FONT_OPTIONS = [
  ...WIDGET_FONT_STACKS,
  { value: WIDGET_CUSTOM_FONT_VALUE, label: 'Custom…' },
]

export interface WidgetAppearanceSectionProps {
  branding: WidgetBrandingInput
  onChange: (next: WidgetBrandingInput) => void
  /** Set by the edit view (a saved widget has an id) so image fields offer a
   * real upload; the create form omits it and gets plain URL inputs. */
  widgetId?: string
}

/** URL-or-upload image field: upload when the widget already exists, plain
 * URL input during creation. */
function ImageField({
  widgetId,
  label,
  value,
  onChange,
  placeholder,
}: {
  widgetId?: string
  label: string
  value: string | null | undefined
  onChange: (url: string | null) => void
  placeholder?: string
}) {
  if (widgetId) {
    return <ImageUploadField widgetId={widgetId} label={label} value={value} onChange={onChange} />
  }
  return (
    <div>
      <label className="text-[13px] font-medium block mb-2">{label} URL</label>
      <Input value={value ?? ''} onChange={e => onChange(e.target.value)} placeholder={placeholder ?? 'https://your-site.com/image.png'} />
    </div>
  )
}

const COMMON_LOCALES: { value: string; label: string }[] = [
  { value: 'es', label: 'Spanish (es)' },
  { value: 'fr', label: 'French (fr)' },
  { value: 'de', label: 'German (de)' },
  { value: 'pt', label: 'Portuguese (pt)' },
  { value: 'it', label: 'Italian (it)' },
  { value: 'hi', label: 'Hindi (hi)' },
  { value: 'ar', label: 'Arabic (ar)' },
  { value: 'he', label: 'Hebrew (he)' },
  { value: 'ur', label: 'Urdu (ur)' },
  { value: 'zh', label: 'Chinese (zh)' },
  { value: 'ja', label: 'Japanese (ja)' },
  { value: 'en', label: 'English (en)' },
]

const LOCALE_COPY_FIELDS: { key: keyof WidgetLocaleCopy & string; label: string }[] = [
  { key: 'header_title', label: 'Header title' },
  { key: 'header_subtitle', label: 'Header subtitle' },
  { key: 'greeting_message', label: 'Greeting message' },
  { key: 'input_placeholder', label: 'Input placeholder' },
  { key: 'loading_text', label: 'Loading indicator text' },
  { key: 'error_message_text', label: 'Error message text' },
  { key: 'offline_message', label: 'Offline message' },
]

const LOCALE_TAG_RE = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$/

function TranslationsEditor({
  branding,
  onChange,
}: {
  branding: WidgetBrandingInput
  onChange: (next: WidgetBrandingInput) => void
}) {
  const locales = branding.locales ?? {}
  const tags = Object.keys(locales)
  const [selected, setSelected] = useState<string | null>(tags[0] ?? null)
  const [addValue, setAddValue] = useState('')

  const setLocales = (next: Record<string, WidgetLocaleCopy>) => onChange({ ...branding, locales: next })

  const addLocale = (tag: string) => {
    const clean = tag.trim().toLowerCase()
    if (!LOCALE_TAG_RE.test(clean) || locales[clean]) return
    setLocales({ ...locales, [clean]: {} })
    setSelected(clean)
    setAddValue('')
  }

  const removeLocale = (tag: string) => {
    const next = { ...locales }
    delete next[tag]
    setLocales(next)
    if (selected === tag) setSelected(Object.keys(next)[0] ?? null)
  }

  const setField = (tag: string, key: string, value: string) => {
    setLocales({ ...locales, [tag]: { ...locales[tag], [key]: value || null } })
  }

  const active = selected ? locales[selected] : null

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {tags.map(tag => (
          <span
            key={tag}
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12px] cursor-pointer border transition-colors ${
              selected === tag
                ? 'border-violet-500 bg-violet-500/10 text-violet-700 dark:text-violet-300'
                : 'border-[var(--border)] text-[var(--text-2)] hover:border-violet-300'
            }`}
            onClick={() => setSelected(tag)}
          >
            {tag}
            <button type="button" aria-label={`Remove ${tag} translation`} onClick={e => { e.stopPropagation(); removeLocale(tag) }}>
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
        <div className="w-[190px]">
          <Select
            value={addValue}
            onValueChange={v => addLocale(v)}
            options={COMMON_LOCALES.filter(l => !locales[l.value])}
            placeholder="Add a language…"
          />
        </div>
      </div>
      {active && selected && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-2)]">
          {LOCALE_COPY_FIELDS.map(({ key, label }) => (
            <div key={key}>
              <label className="text-[12px] text-[var(--text-3)] block mb-1.5">{label}</label>
              <Input
                value={(active[key] as string | null | undefined) ?? ''}
                onChange={e => setField(selected, key, e.target.value)}
                placeholder="Uses default copy"
              />
            </div>
          ))}
          <div className="sm:col-span-2">
            <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Quick replies (one per line — leave empty to reuse the defaults)</label>
            <Textarea
              value={(active.quick_replies ?? []).join('\n')}
              onChange={e => {
                const lines = e.target.value.split('\n').map(l => l.trim()).filter(Boolean)
                setLocales({ ...locales, [selected]: { ...active, quick_replies: lines.length ? lines : null } })
              }}
              rows={3}
            />
          </div>
        </div>
      )}
    </div>
  )
}

/** The full Appearance tab, shared verbatim between WidgetCreateForm and
 * WidgetDetailView (it used to be duplicated in both). Controlled-value
 * pattern mirrors WidgetAdvancedSectionProps; save buttons live in the
 * callers. */
export function WidgetAppearanceSection({ branding, onChange, widgetId }: WidgetAppearanceSectionProps) {
  const [quickReplyDraft, setQuickReplyDraft] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(!!branding.custom_css)
  const [allStylingOpen, setAllStylingOpen] = useState(false)
  // Once the admin picks "Custom…" we keep the free-text input visible even
  // while they type a value that happens to match a curated stack.
  const [customFont, setCustomFont] = useState(
    () => !WIDGET_FONT_STACKS.some(f => f.value === (branding.font_family ?? 'system-ui')),
  )

  const set = (patch: Partial<WidgetBrandingInput>) => onChange({ ...branding, ...patch })

  const [extractingColors, setExtractingColors] = useState(false)
  const handleExtractBrandColors = async () => {
    if (!branding.header_logo_url) return
    setExtractingColors(true)
    try {
      const colors = await extractBrandColors(branding.header_logo_url)
      if (colors) {
        set({ theme_color: colors.primary, secondary_color: colors.secondary })
      }
    } finally {
      setExtractingColors(false)
    }
  }

  const addQuickReply = () => {
    const value = quickReplyDraft.trim()
    if (!value || (branding.quick_replies ?? []).includes(value)) return
    set({ quick_replies: [...(branding.quick_replies ?? []), value] })
    setQuickReplyDraft('')
  }

  const removeQuickReply = (value: string) => {
    set({ quick_replies: (branding.quick_replies ?? []).filter(q => q !== value) })
  }

  const fontSelectValue = customFont
    ? WIDGET_CUSTOM_FONT_VALUE
    : WIDGET_FONT_STACKS.some(f => f.value === (branding.font_family ?? 'system-ui'))
      ? branding.font_family ?? 'system-ui'
      : WIDGET_CUSTOM_FONT_VALUE

  const customCssLength = (branding.custom_css ?? '').length

  return (
    <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-6">
      {/* Essentials: the six controls almost every admin touches. Everything
          else lives behind the "All styling options" disclosure below. */}
      <div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-[13px] font-medium block mb-2">Header title</label>
            <Input value={branding.header_title ?? ''} onChange={e => set({ header_title: e.target.value })} />
          </div>
          <ImageField
            widgetId={widgetId}
            label="Logo"
            value={branding.header_logo_url}
            onChange={url => set({ header_logo_url: url })}
            placeholder="https://your-site.com/logo.png"
          />
        </div>
        <div className="flex items-center justify-between mt-4 mb-2">
          <p className="text-[13px] font-medium">Theme</p>
          {branding.header_logo_url && (
            <Button
              variant="ghost"
              size="xs"
              onClick={handleExtractBrandColors}
              disabled={extractingColors}
              title="Sample your logo's dominant colors and apply them as primary/secondary"
            >
              {extractingColors ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5 mr-1.5" />}
              Use logo colors
            </Button>
          )}
        </div>
        <div className="mb-4">
          <ThemePresetPicker current={branding} onApply={preset => onChange({ ...branding, ...preset })} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <ColorField
            label="Primary color"
            value={branding.theme_color}
            onChange={v => set({ theme_color: v })}
            placeholder="#4F46E5"
          />
          <div>
            <label className="text-[13px] font-medium block mb-2">Font family</label>
            <Select
              value={fontSelectValue}
              onValueChange={v => {
                if (v === WIDGET_CUSTOM_FONT_VALUE) {
                  setCustomFont(true)
                } else {
                  setCustomFont(false)
                  set({ font_family: v })
                }
              }}
              options={FONT_OPTIONS}
            />
            {fontSelectValue === WIDGET_CUSTOM_FONT_VALUE && (
              <Input
                value={branding.font_family ?? ''}
                onChange={e => set({ font_family: e.target.value })}
                placeholder="'My Brand Font', system-ui, sans-serif"
                className="mt-2"
              />
            )}
          </div>
          <div className="sm:col-span-2">
            <label className="text-[13px] font-medium block mb-2">Greeting message</label>
            <Input value={branding.greeting_message ?? ''} onChange={e => set({ greeting_message: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="text-[13px] font-medium block mb-2">Quick replies</label>
            <p className="text-[11px] text-[var(--text-3)] mb-2">Canned questions shown as chips under the greeting.</p>
            <div className="flex gap-2">
              <Input
                value={quickReplyDraft}
                onChange={e => setQuickReplyDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addQuickReply() } }}
                placeholder="What are your pricing plans?"
              />
              <Button variant="outline" onClick={addQuickReply}>Add</Button>
            </div>
            {(branding.quick_replies ?? []).length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {(branding.quick_replies ?? []).map(q => (
                  <span key={q} className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300 rounded-full px-2.5 py-1 text-[12px]">
                    {q}
                    <button type="button" onClick={() => removeQuickReply(q)}><X className="w-3 h-3" /></button>
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={!!branding.dark_mode} onChange={e => set({ dark_mode: e.target.checked })} className="w-4 h-4 accent-violet-600" />
              <span className="text-[13px]">Dark mode</span>
            </label>
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-[var(--border)]">
        <button
          type="button"
          onClick={() => setAllStylingOpen(v => !v)}
          className="flex items-center gap-1.5 text-[13px] font-medium text-[var(--text-2)] hover:text-[var(--text-1)] transition-colors"
        >
          <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-150 ${allStylingOpen ? '' : '-rotate-90'}`} />
          All styling options
          <span className="text-[11px] font-normal text-[var(--text-3)]">&mdash; header colors, bubbles, avatars, copy, typography</span>
        </button>
        {allStylingOpen && (
          <div className="mt-4 space-y-6">
            <div>
              <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Header details</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-[13px] font-medium block mb-2">Subtitle</label>
                  <Input value={branding.header_subtitle ?? ''} onChange={e => set({ header_subtitle: e.target.value })} placeholder="We usually reply in a few minutes" />
                </div>
                <ColorField
                  label="Header background"
                  value={branding.header_bg_color}
                  onChange={v => set({ header_bg_color: v })}
                  placeholder="Falls back to theme color"
                  fallbackColor={branding.theme_color || '#4F46E5'}
                />
                <ColorField
                  label="Header text color"
                  value={branding.header_text_color}
                  onChange={v => set({ header_text_color: v })}
                  placeholder="Auto"
                  fallbackColor="#111827"
                />
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border)]">
              <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Colors &amp; typography</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ColorField
                  label="Secondary color"
                  value={branding.secondary_color}
                  onChange={v => set({ secondary_color: v })}
                  placeholder="#818CF8"
                  fallbackColor="#818CF8"
                />
                <ColorField
                  label="Background color"
                  value={branding.background_color}
                  onChange={v => set({ background_color: v })}
                  placeholder="Auto (light/dark mode)"
                  fallbackColor={branding.dark_mode ? '#111827' : '#ffffff'}
                />
                <ColorField
                  label="Text color"
                  value={branding.text_color}
                  onChange={v => set({ text_color: v })}
                  placeholder="Auto (light/dark mode)"
                  fallbackColor={branding.dark_mode ? '#f3f4f6' : '#111827'}
                />
                <ColorField
                  label="Border color"
                  value={branding.border_color}
                  onChange={v => set({ border_color: v })}
                  placeholder="Auto"
                  fallbackColor={branding.dark_mode ? '#374151' : '#e5e7eb'}
                />
                <div>
                  <label className="text-[13px] font-medium block mb-2">Base font size (px)</label>
                  <Input type="number" value={branding.font_size_base ?? 14} onChange={e => set({ font_size_base: Number(e.target.value) })} />
                </div>
                <div>
                  <label className="text-[13px] font-medium block mb-2">Font weight</label>
                  <Select
                    value={branding.font_weight ?? 'normal'}
                    onValueChange={v => set({ font_weight: v as WidgetBrandingInput['font_weight'] })}
                    options={[{ value: 'normal', label: 'Normal' }, { value: 'medium', label: 'Medium' }, { value: 'bold', label: 'Bold' }]}
                  />
                </div>
                <div>
                  <label className="text-[13px] font-medium block mb-2">Text direction</label>
                  <Select
                    value={branding.text_direction ?? 'auto'}
                    onValueChange={v => set({ text_direction: v as WidgetTextDirection })}
                    options={TEXT_DIRECTION_OPTIONS}
                  />
                </div>
                <div className="flex items-end pb-1">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={branding.show_branding !== false} onChange={e => set({ show_branding: e.target.checked })} className="w-4 h-4 accent-violet-600" />
                    <span className="text-[13px]">Show &quot;Powered by&quot; branding</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border)]">
              <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Avatars &amp; message bubbles</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ImageField
                  widgetId={widgetId}
                  label="Assistant avatar"
                  value={branding.assistant_avatar_url}
                  onChange={url => set({ assistant_avatar_url: url })}
                />
                <ImageField
                  widgetId={widgetId}
                  label="Visitor avatar"
                  value={branding.user_avatar_url}
                  onChange={url => set({ user_avatar_url: url })}
                />
                <ColorField
                  label="Assistant bubble color"
                  value={branding.assistant_bubble_color}
                  onChange={v => set({ assistant_bubble_color: v })}
                  placeholder="Auto"
                  fallbackColor={branding.dark_mode ? '#1f2937' : '#f3f4f6'}
                />
                <ColorField
                  label="Visitor bubble color"
                  value={branding.user_bubble_color}
                  onChange={v => set({ user_bubble_color: v })}
                  placeholder="Falls back to theme color"
                  fallbackColor={branding.theme_color || '#4F46E5'}
                />
                <div className="flex items-end pb-1">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={!!branding.show_avatars_in_messages} onChange={e => set({ show_avatars_in_messages: e.target.checked })} className="w-4 h-4 accent-violet-600" />
                    <span className="text-[13px]">Show avatars next to messages</span>
                  </label>
                </div>
                <div className="flex items-end pb-1">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={!!branding.show_timestamps} onChange={e => set({ show_timestamps: e.target.checked })} className="w-4 h-4 accent-violet-600" />
                    <span className="text-[13px]">Show message timestamps</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border)]">
              <p className="text-[14px] font-semibold text-[var(--text-1)] mb-3">Input &amp; system copy</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-[13px] font-medium block mb-2">Input placeholder</label>
                  <Input value={branding.input_placeholder ?? ''} onChange={e => set({ input_placeholder: e.target.value })} />
                </div>
                <ColorField
                  label="Send button color"
                  value={branding.send_button_color}
                  onChange={v => set({ send_button_color: v })}
                  placeholder="Falls back to theme color"
                  fallbackColor={branding.theme_color || '#4F46E5'}
                />
                <div>
                  <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Loading indicator text</label>
                  <Input value={branding.loading_text ?? ''} onChange={e => set({ loading_text: e.target.value })} />
                </div>
                <div>
                  <label className="text-[12px] text-[var(--text-3)] block mb-1.5">Error message text</label>
                  <Input value={branding.error_message_text ?? ''} onChange={e => set({ error_message_text: e.target.value })} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="pt-4 border-t border-[var(--border)]">
        <p className="text-[14px] font-semibold text-[var(--text-1)] mb-1">Translations</p>
        <p className="text-[11px] text-[var(--text-3)] mb-3">
          Per-language overrides for the visitor-facing copy. The widget picks the visitor&apos;s browser
          language automatically (exact tag first, e.g. <code>fr-CA</code>, then base language <code>fr</code>);
          anything left blank falls back to the default copy above.
        </p>
        <TranslationsEditor branding={branding} onChange={onChange} />
      </div>

      <div className="pt-4 border-t border-[var(--border)]">
        <button
          type="button"
          onClick={() => setAdvancedOpen(v => !v)}
          className="flex items-center gap-1.5 text-[13px] font-medium text-[var(--text-2)] hover:text-[var(--text-1)] transition-colors"
        >
          <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-150 ${advancedOpen ? '' : '-rotate-90'}`} />
          Advanced
        </button>
        {advancedOpen && (
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-[13px] font-medium">Custom CSS</label>
              <span className={`text-[11px] ${customCssLength > CUSTOM_CSS_MAX ? 'text-red-500 dark:text-red-400' : 'text-[var(--text-3)]'}`}>
                {customCssLength.toLocaleString()} / {CUSTOM_CSS_MAX.toLocaleString()}
              </span>
            </div>
            <Textarea
              value={branding.custom_css ?? ''}
              onChange={e => set({ custom_css: e.target.value || null })}
              rows={8}
              spellCheck={false}
              placeholder={'.oneai-widget .message { border-radius: 4px; }'}
              className="font-mono text-[12.5px] leading-relaxed"
            />
            <p className="text-[11px] text-[var(--text-3)]">
              Applied inside the widget iframe only — it can&apos;t affect the host page. Selectors and internal
              markup aren&apos;t a stable API, so custom CSS is unsupported territory: it may break on any update.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
