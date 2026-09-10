'use client'

import { useState } from 'react'
import { Check, ExternalLink } from 'lucide-react'
import { WidgetMarkdown } from '@/components/widget/WidgetMarkdown'
import { readableTextOn } from '@/lib/widget-styles'

/** Inline form emitted via a ```form fence. Submitting composes the values
 * into a labeled plain-text message ("Name: …") and sends it as the visitor's
 * message, so the agent (and the transcript) see exactly what was entered. */
function RichInlineForm({
  form,
  themeColor,
  buttonText,
  onSend,
  disabled,
  large,
}: {
  form: { title?: string; submit_label?: string; fields: Array<{ name: string; label: string; type: string; required?: boolean; placeholder?: string }> }
  themeColor: string
  buttonText: string
  onSend?: (text: string) => void
  disabled?: boolean
  large?: boolean
}) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const labelSize = large ? 'text-[12.5px]' : 'text-[11.5px]'
  const inputSize = large ? 'text-[14px]' : 'text-[12.5px]'

  const handleSubmit = () => {
    if (!onSend || disabled || submitted) return
    const missing = form.fields.filter(f => f.required !== false && !(values[f.name] ?? '').trim())
    if (missing.length) {
      setError(`Please fill in: ${missing.map(f => f.label).join(', ')}`)
      return
    }
    setError(null)
    const lines = form.fields
      .map(f => ({ f, v: (values[f.name] ?? '').trim() }))
      .filter(({ v }) => v)
      .map(({ f, v }) => `${f.label}: ${v}`)
    onSend(lines.join('\n'))
    setSubmitted(true)
  }

  return (
    <div className="my-2 p-3 rounded-xl border space-y-2" style={{ borderColor: 'rgba(128,128,128,0.25)' }}>
      {form.title && <p className={`font-semibold ${large ? 'text-[14px]' : 'text-[13px]'}`}>{form.title}</p>}
      {form.fields.map(f => (
        <div key={f.name}>
          <label className={`block mb-1 opacity-70 ${labelSize}`}>
            {f.label}
            {f.required !== false && <span className="opacity-60"> *</span>}
          </label>
          {f.type === 'textarea' ? (
            <textarea
              value={values[f.name] ?? ''}
              onChange={e => setValues(prev => ({ ...prev, [f.name]: e.target.value }))}
              disabled={submitted}
              rows={3}
              placeholder={f.placeholder}
              className={`w-full rounded-lg px-2.5 py-1.5 border bg-transparent outline-none resize-none disabled:opacity-60 ${inputSize}`}
              style={{ borderColor: 'rgba(128,128,128,0.35)' }}
            />
          ) : (
            <input
              type={f.type === 'email' ? 'email' : f.type === 'phone' ? 'tel' : 'text'}
              value={values[f.name] ?? ''}
              onChange={e => setValues(prev => ({ ...prev, [f.name]: e.target.value }))}
              disabled={submitted}
              placeholder={f.placeholder}
              className={`w-full rounded-lg px-2.5 py-1.5 border bg-transparent outline-none disabled:opacity-60 ${inputSize}`}
              style={{ borderColor: 'rgba(128,128,128,0.35)' }}
            />
          )}
        </div>
      ))}
      {error && <p className={`text-red-500 ${labelSize}`}>{error}</p>}
      <button
        type="button"
        disabled={disabled || submitted || !onSend}
        onClick={handleSubmit}
        className={`w-full rounded-lg py-1.5 font-medium transition-opacity hover:opacity-90 disabled:opacity-60 inline-flex items-center justify-center gap-1.5 ${inputSize}`}
        style={{ backgroundColor: themeColor, color: buttonText }}
      >
        {submitted && <Check className="w-3.5 h-3.5" />}
        {submitted ? 'Sent' : form.submit_label || 'Submit'}
      </button>
    </div>
  )
}

/**
 * Structured rich messages for the embed, layered on top of plain markdown.
 *
 * Agents opt in by emitting fenced blocks the widget understands:
 *
 *   ```buttons
 *   ["Track my order", {"label": "Talk to sales", "value": "I want to talk to sales"}]
 *   ```
 *
 *   ```cards
 *   [{"title": "Pro plan", "description": "For growing teams", "image_url": "…",
 *     "link_url": "https://…", "link_label": "See pricing", "button": "Choose Pro"}]
 *   ```
 *
 * Everything outside those fences renders as normal markdown. A malformed
 * block degrades to a plain code block (WidgetMarkdown's default), so a
 * half-streamed or invalid payload can never blank a reply.
 */

export interface RichButton {
  label: string
  /** Message text sent when tapped; defaults to the label. */
  value: string
}

export interface RichCard {
  title: string
  description?: string
  image_url?: string
  link_url?: string
  link_label?: string
  /** Optional tap-to-send button under the card. */
  button?: string
  button_value?: string
}

export interface RichFormField {
  name: string
  label: string
  type: 'text' | 'email' | 'phone' | 'textarea'
  required?: boolean
  placeholder?: string
}

export interface RichForm {
  title?: string
  submit_label?: string
  fields: RichFormField[]
}

type Segment =
  | { kind: 'markdown'; text: string }
  | { kind: 'buttons'; buttons: RichButton[] }
  | { kind: 'cards'; cards: RichCard[] }
  | { kind: 'form'; form: RichForm }

const FENCE_RE = /```(buttons|cards|form)\n([\s\S]*?)```/g

const FORM_FIELD_TYPES = new Set(['text', 'email', 'phone', 'textarea'])

function parseForm(body: string): RichForm | null {
  try {
    const raw = JSON.parse(body)
    if (!raw || typeof raw !== 'object' || !Array.isArray(raw.fields)) return null
    const fields = raw.fields
      .filter(
        (f: unknown): f is RichFormField =>
          !!f && typeof f === 'object' &&
          typeof (f as RichFormField).name === 'string' && (f as RichFormField).name.trim() !== '' &&
          typeof (f as RichFormField).label === 'string' && (f as RichFormField).label.trim() !== '',
      )
      .map((f: RichFormField): RichFormField => ({ ...f, type: FORM_FIELD_TYPES.has(f.type) ? f.type : 'text' }))
      .slice(0, 8)
    if (!fields.length) return null
    return {
      title: typeof raw.title === 'string' ? raw.title : undefined,
      submit_label: typeof raw.submit_label === 'string' ? raw.submit_label : undefined,
      fields,
    }
  } catch {
    return null
  }
}

function parseButtons(body: string): RichButton[] | null {
  try {
    const raw = JSON.parse(body)
    if (!Array.isArray(raw) || raw.length === 0) return null
    const buttons = raw
      .map((b): RichButton | null => {
        if (typeof b === 'string') return b.trim() ? { label: b.trim(), value: b.trim() } : null
        if (b && typeof b === 'object' && typeof b.label === 'string' && b.label.trim()) {
          return { label: b.label.trim(), value: (typeof b.value === 'string' && b.value.trim()) || b.label.trim() }
        }
        return null
      })
      .filter((b): b is RichButton => b !== null)
    return buttons.length ? buttons.slice(0, 8) : null
  } catch {
    return null
  }
}

function parseCards(body: string): RichCard[] | null {
  try {
    const raw = JSON.parse(body)
    if (!Array.isArray(raw) || raw.length === 0) return null
    const cards = raw.filter(
      (c): c is RichCard => !!c && typeof c === 'object' && typeof c.title === 'string' && c.title.trim() !== '',
    )
    return cards.length ? cards.slice(0, 10) : null
  } catch {
    return null
  }
}

export function parseRichSegments(content: string): Segment[] {
  const segments: Segment[] = []
  let last = 0
  for (const match of content.matchAll(FENCE_RE)) {
    const index = match.index ?? 0
    const parsed = match[1] === 'buttons' ? parseButtons(match[2]) : null
    const parsedCards = match[1] === 'cards' ? parseCards(match[2]) : null
    const parsedForm = match[1] === 'form' ? parseForm(match[2]) : null
    if (!parsed && !parsedCards && !parsedForm) continue // malformed → leave inside the surrounding markdown
    if (index > last) segments.push({ kind: 'markdown', text: content.slice(last, index) })
    if (parsed) segments.push({ kind: 'buttons', buttons: parsed })
    if (parsedCards) segments.push({ kind: 'cards', cards: parsedCards })
    if (parsedForm) segments.push({ kind: 'form', form: parsedForm })
    last = index + match[0].length
  }
  if (last < content.length) segments.push({ kind: 'markdown', text: content.slice(last) })
  return segments.length ? segments : [{ kind: 'markdown', text: content }]
}

interface WidgetRichContentProps {
  content: string
  themeColor: string
  /** Sends the tapped button/card value as a visitor message. */
  onSend?: (text: string) => void
  /** True while a reply is in flight — buttons render but don't fire. */
  disabled?: boolean
  large?: boolean
}

export function WidgetRichContent({ content, themeColor, onSend, disabled, large }: WidgetRichContentProps) {
  const segments = parseRichSegments(content)
  const buttonText = readableTextOn(themeColor)

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.kind === 'markdown') {
          const text = seg.text.trim()
          return text ? <WidgetMarkdown key={i} content={text} /> : null
        }
        if (seg.kind === 'form') {
          return (
            <RichInlineForm
              key={i}
              form={seg.form}
              themeColor={themeColor}
              buttonText={buttonText}
              onSend={onSend}
              disabled={disabled}
              large={large}
            />
          )
        }
        if (seg.kind === 'buttons') {
          return (
            <div key={i} className="flex flex-wrap gap-2 my-2">
              {seg.buttons.map((b, j) => (
                <button
                  key={j}
                  type="button"
                  disabled={disabled || !onSend}
                  onClick={() => onSend?.(b.value)}
                  className={`rounded-full px-3 py-1.5 border font-medium transition-colors disabled:opacity-60 ${large ? 'text-[13px]' : 'text-[12px]'}`}
                  style={{ borderColor: themeColor, color: themeColor }}
                  onMouseEnter={e => { e.currentTarget.style.backgroundColor = themeColor; e.currentTarget.style.color = buttonText }}
                  onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = themeColor }}
                >
                  {b.label}
                </button>
              ))}
            </div>
          )
        }
        return (
          <div key={i} className="flex gap-2.5 my-2 overflow-x-auto pb-1 -mx-1 px-1 snap-x">
            {seg.cards.map((c, j) => (
              <div
                key={j}
                className="w-[200px] shrink-0 snap-start rounded-xl border overflow-hidden bg-white/60 dark:bg-black/20"
                style={{ borderColor: 'rgba(128,128,128,0.25)' }}
              >
                {c.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.image_url} alt="" loading="lazy" className="w-full h-[100px] object-cover" />
                )}
                <div className="p-2.5 space-y-1">
                  <p className={`font-semibold leading-snug ${large ? 'text-[14px]' : 'text-[13px]'}`}>{c.title}</p>
                  {c.description && (
                    <p className={`opacity-70 leading-snug ${large ? 'text-[12.5px]' : 'text-[11.5px]'}`}>{c.description}</p>
                  )}
                  <div className="flex flex-col gap-1.5 pt-1">
                    {c.link_url && (
                      <a
                        href={c.link_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`inline-flex items-center gap-1 font-medium hover:underline ${large ? 'text-[12.5px]' : 'text-[11.5px]'}`}
                        style={{ color: themeColor }}
                      >
                        {c.link_label || 'Learn more'}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {c.button && (
                      <button
                        type="button"
                        disabled={disabled || !onSend}
                        onClick={() => onSend?.(c.button_value || c.button!)}
                        className={`rounded-lg px-2.5 py-1.5 font-medium transition-opacity hover:opacity-90 disabled:opacity-60 ${large ? 'text-[12.5px]' : 'text-[11.5px]'}`}
                        style={{ backgroundColor: themeColor, color: buttonText }}
                      >
                        {c.button}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      })}
    </>
  )
}
