'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Check, Copy, Paperclip, RotateCcw, Sparkles, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import type { WidgetBranding, WidgetLayout, WidgetTextDirection } from '@/types'
import {
  avatarTileBackground,
  bubbleRadiusFor,
  deriveWidgetColors,
  readableTextOn,
  sendButtonBorderRadius,
  spacingFor,
} from '@/lib/widget-styles'
import { WidgetRichContent } from '@/components/widget/WidgetRichContent'

interface Accessibility {
  reduced_motion: boolean
  high_contrast: boolean
  large_text: boolean
}

interface DaySchedule {
  enabled: boolean
  start: string
  end: string
}

interface Availability {
  enabled: boolean
  timezone: string
  schedule: Record<string, DaySchedule>
  offline_message: string
}

interface LeadField {
  field_name: string
  label: string
  field_type: 'text' | 'email' | 'phone'
  required: boolean
}

/** Attachment reference returned by the parent's POST /widget/{id}/upload
 * call -- shaped defensively since the backend contract is `{url, ...}` with
 * optional extras. Sent back verbatim in the message body's `attachments`. */
interface AttachmentRef {
  url?: string
  attachment_id?: string
  filename?: string
  content_type?: string
  [key: string]: unknown
}

interface PendingAttachment {
  uploadId: string
  name: string
  status: 'uploading' | 'ready' | 'error'
  ref?: AttachmentRef
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  at: number
  /** Assistant message still streaming in. */
  pending?: boolean
  /** User message that could not be delivered -- shows the Retry affordance. */
  failed?: boolean
  /** Chips rendered inside a user bubble + payload replayed on retry. */
  attachments?: AttachmentRef[]
}

function generateMessageId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const MAX_ATTACHMENTS = 5
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
const ATTACHMENT_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp,.pdf,.txt'
const TEXTAREA_MAX_HEIGHT = 110 // ~5 rows at 13px/relaxed

const DEFAULT_BRANDING: WidgetBranding = {
  theme_color: '#4F46E5',
  position: 'bottom-right',
  header_title: 'Chat with us',
  header_subtitle: null,
  header_logo_url: null,
  header_text_color: '#111827',
  header_bg_color: null,
  greeting_message: 'Hi! How can I help you today?',
  dark_mode: false,
  font_family: 'system-ui',
  font_size_base: 14,
  font_weight: 'normal',
  secondary_color: '#818CF8',
  background_color: null,
  text_color: null,
  border_color: null,
  assistant_avatar_url: null,
  user_avatar_url: null,
  show_avatars_in_messages: false,
  user_bubble_color: null,
  assistant_bubble_color: null,
  show_timestamps: false,
  input_placeholder: 'Type a message…',
  send_button_color: null,
  loading_text: 'Thinking…',
  empty_state_text: 'No messages yet. Say hello!',
  error_message_text: 'Something went wrong. Please try again.',
  quick_replies: [],
  show_branding: true,
  custom_css: null,
  text_direction: 'auto',
}

const DEFAULT_LAYOUT: WidgetLayout = {
  widget_width: 380,
  widget_height: 600,
  widget_min_width: 300,
  widget_min_height: 400,
  widget_max_width: 480,
  widget_max_height: 760,
  launcher_size: 56,
  launcher_shape: 'circle',
  launcher_icon: 'chat',
  launcher_icon_url: null,
  launcher_hover_effect: 'scale',
  offset_x: 20,
  offset_y: 20,
  border_radius: 16,
  shadow_style: 'medium',
  bubble_style: 'rounded',
  send_button_shape: 'square',
  spacing_density: 'comfortable',
  animation_style: 'fade',
  mobile_full_screen: true,
  mobile_breakpoint_px: 640,
}

const DAY_INDEX_TO_KEY = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']

/** Built-in micro-strings (everything NOT admin-configurable copy), keyed by
 * base language. Admin copy (greeting, placeholder, …) is localized via
 * branding.locales in widget.js; this covers the widget's own chrome. */
const UI_STRINGS: Record<string, { online: string; away: string; continue_: string; enterHint: string; newline: string }> = {
  en: { online: 'Online', away: 'Away', continue_: 'Continue', enterHint: 'to send', newline: 'for new line' },
  es: { online: 'En línea', away: 'Ausente', continue_: 'Continuar', enterHint: 'para enviar', newline: 'para nueva línea' },
  fr: { online: 'En ligne', away: 'Absent', continue_: 'Continuer', enterHint: 'pour envoyer', newline: 'pour un saut de ligne' },
  de: { online: 'Online', away: 'Abwesend', continue_: 'Weiter', enterHint: 'zum Senden', newline: 'für neue Zeile' },
  pt: { online: 'Online', away: 'Ausente', continue_: 'Continuar', enterHint: 'para enviar', newline: 'para nova linha' },
  it: { online: 'Online', away: 'Assente', continue_: 'Continua', enterHint: 'per inviare', newline: 'per andare a capo' },
  hi: { online: 'ऑनलाइन', away: 'दूर', continue_: 'जारी रखें', enterHint: 'भेजने के लिए', newline: 'नई पंक्ति के लिए' },
  ar: { online: 'متصل', away: 'غير متواجد', continue_: 'متابعة', enterHint: 'للإرسال', newline: 'لسطر جديد' },
  he: { online: 'מחובר', away: 'לא זמין', continue_: 'המשך', enterHint: 'לשליחה', newline: 'לשורה חדשה' },
  ur: { online: 'آن لائن', away: 'غیر حاضر', continue_: 'جاری رکھیں', enterHint: 'بھیجنے کے لیے', newline: 'نئی سطر کے لیے' },
  zh: { online: '在线', away: '离开', continue_: '继续', enterHint: '发送', newline: '换行' },
  ja: { online: 'オンライン', away: '離席中', continue_: '続ける', enterHint: 'で送信', newline: 'で改行' },
}

const RTL_LANGUAGES = new Set(['ar', 'he', 'fa', 'ur'])

function uiStringsFor(locale: string | null) {
  const base = (locale ?? 'en').toLowerCase().split('-')[0]
  return UI_STRINGS[base] ?? UI_STRINGS.en
}

/** A short, synthesized beep -- no audio asset to host/load. */
function playNotificationSound() {
  try {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioContextClass) return
    const ctx = new AudioContextClass()
    const oscillator = ctx.createOscillator()
    const gain = ctx.createGain()
    oscillator.type = 'sine'
    oscillator.frequency.value = 660
    gain.gain.setValueAtTime(0.15, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2)
    oscillator.connect(gain)
    gain.connect(ctx.destination)
    oscillator.start()
    oscillator.stop(ctx.currentTime + 0.2)
  } catch {
    /* audio unsupported/blocked -- silently skip */
  }
}

/** Business-hours gating. The instant (`new Date()`) is an absolute moment
 * shared by every clock on Earth -- `Intl.DateTimeFormat` with an explicit
 * `timeZone` always converts it into the widget's CONFIGURED timezone,
 * independent of the visitor's own device timezone (verified: the same UTC
 * instant formats identically regardless of the visitor's locale/TZ). The
 * only real dependency on the visitor's side is their device clock being
 * roughly accurate, same as any client-only scheduling check.
 *
 * Handles overnight windows (e.g. 22:00-02:00 for a night-shift team):
 * checks both today's schedule and, for a window that started yesterday and
 * wraps past midnight, yesterday's schedule too. */
function minutesOf(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

function withinWindow(nowMinutes: number, day: DaySchedule | undefined, wrapped: 'start-side' | 'end-side'): boolean {
  if (!day?.enabled) return false
  const start = minutesOf(day.start)
  const end = minutesOf(day.end)
  if (start <= end) {
    // Same-day window (the common case) -- only relevant checked "as today".
    return wrapped === 'start-side' && nowMinutes >= start && nowMinutes <= end
  }
  // Overnight window: the stretch from `start` to midnight belongs to "today"
  // (start-side), and the stretch from midnight to `end` belongs to the NEXT
  // calendar day (end-side), which is why the caller also checks yesterday.
  return wrapped === 'start-side' ? nowMinutes >= start : nowMinutes <= end
}

function isCurrentlyAvailable(availability: Availability | null): boolean {
  if (!availability || !availability.enabled) return true
  try {
    const now = new Date()
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: availability.timezone || 'UTC',
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(now)
    const weekdayShort = (parts.find(p => p.type === 'weekday')?.value.toLowerCase().slice(0, 3) ?? 'sun') as (typeof DAY_INDEX_TO_KEY)[number]
    const hour = parts.find(p => p.type === 'hour')?.value ?? '00'
    const minute = parts.find(p => p.type === 'minute')?.value ?? '00'
    const nowMinutes = parseInt(hour, 10) * 60 + parseInt(minute, 10)

    const todayIndex = DAY_INDEX_TO_KEY.indexOf(weekdayShort)
    const yesterdayKey = DAY_INDEX_TO_KEY[(todayIndex + 6) % 7]

    const today = availability.schedule?.[weekdayShort]
    const yesterday = availability.schedule?.[yesterdayKey]

    return withinWindow(nowMinutes, today, 'start-side') || withinWindow(nowMinutes, yesterday, 'end-side')
  } catch {
    return true
  }
}

/** Freshness-first timestamp: "just now" / "4m ago" within the hour, clock
 * time for today, short date beyond -- matches how visitors actually think
 * about a chat ("did this just happen?"), not wall-clock precision. */
function formatTime(at: number): string {
  const ageMs = Date.now() - at
  if (ageMs < 60_000) return 'just now'
  if (ageMs < 3_600_000) return `${Math.floor(ageMs / 60_000)}m ago`
  const d = new Date(at)
  if (d.toDateString() === new Date().toDateString()) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

/** Stable assistant-message id for the reply streaming in for a given user
 * message, so successive oneai:assistant-delta events target one bubble. */
function assistantIdFor(clientId: string): string {
  return `assistant-${clientId}`
}

/**
 * Pure rendering surface -- this page never calls the backend API itself.
 * Every network call (config/session/message/lead/upload) is made by the
 * parent widget.js script, which runs in the HOST PAGE's origin -- so the
 * Origin header the backend's allowlist checks against is genuinely the
 * customer site embedding the widget, not this iframe's own origin (which is
 * always this app's domain, regardless of who embeds it). This page only ever
 * exchanges postMessage with its parent. Style derivation (colors, bubble
 * radius, spacing, shadows) is shared with WidgetLivePreview via
 * lib/widget-styles.ts so the admin preview and this real embed can't drift.
 *
 * Note on iframe -> parent postMessage targeting '*': the widget is embedded
 * on arbitrary customer origins this iframe cannot know in advance, so a
 * concrete targetOrigin is impossible by design. Nothing posted upward is
 * secret (the parent page already sees all of it), and the parent validates
 * event.source before acting. Parent -> iframe messages DO target this
 * iframe's concrete origin -- see public/widget.js.
 */
export default function EmbedWidgetPage() {
  const [branding, setBranding] = useState<WidgetBranding>(DEFAULT_BRANDING)
  const [layout, setLayout] = useState<WidgetLayout>(DEFAULT_LAYOUT)
  const [accessibility, setAccessibility] = useState<Accessibility>({ reduced_motion: false, high_contrast: false, large_text: false })
  const [availability, setAvailability] = useState<Availability | null>(null)
  const [leadFields, setLeadFields] = useState<LeadField[]>([])
  const [leadValues, setLeadValues] = useState<Record<string, string>>({})
  const [leadSubmitted, setLeadSubmitted] = useState(false)
  const [ready, setReady] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [feedback, setFeedback] = useState<Record<string, 'up' | 'down'>>({})
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [online, setOnline] = useState(true)
  const [allowAttachments, setAllowAttachments] = useState(false)
  const [locale, setLocale] = useState<string | null>(null)
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([])
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState('')
  // Engine progress ("Using Web Search…") shown in place of loading_text
  // while the typing indicator is up; cleared once the reply lands.
  const [statusText, setStatusText] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Ref, not state -- the message listener below is attached once (empty
  // effect deps) and would otherwise close over welcomeSound's stale initial
  // value for the lifetime of the iframe.
  const welcomeSoundRef = useRef(false)

  const finalizeAssistant = useCallback((content: string) => {
    setSending(false)
    setStreaming(false)
    setStatusText(null)
    setAnnouncement(content)
    if (welcomeSoundRef.current) playNotificationSound()
  }, [])

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.source !== window.parent) return
      const data = event.data
      if (!data || typeof data !== 'object') return

      if (data.type === 'oneai:init') {
        const nextBranding: WidgetBranding = { ...DEFAULT_BRANDING, ...(data.payload?.branding ?? {}) }
        const nextLayout: WidgetLayout = { ...DEFAULT_LAYOUT, ...(data.payload?.layout ?? {}) }
        const greeting: string = data.payload?.greeting ?? nextBranding.greeting_message
        const fields: LeadField[] = data.payload?.leadFields ?? []
        setBranding(nextBranding)
        setLayout(nextLayout)
        setAccessibility(data.payload?.accessibility ?? { reduced_motion: false, high_contrast: false, large_text: false })
        setAvailability(data.payload?.availability ?? null)
        setLeadFields(fields)
        setAllowAttachments(!!data.payload?.allowAttachments)
        setLocale(data.payload?.locale ?? null)
        setOnline(data.payload?.online !== false)
        welcomeSoundRef.current = !!data.payload?.welcomeSound
        setMessages([{ id: generateMessageId(), role: 'assistant', content: greeting, at: Date.now() }])
        setReady(true)
      } else if (data.type === 'oneai:assistant-delta') {
        const p = data.payload ?? {}
        const clientId: string = p.clientId ?? 'stream'
        const assistantId = assistantIdFor(clientId)
        if (p.kind === 'start') {
          // Nothing visible yet -- the typing indicator keeps running until
          // the first token (or the done event) arrives.
        } else if (p.kind === 'delta') {
          const text: string = p.text ?? ''
          setStatusText(null)
          setMessages(prev => {
            const existing = prev.find(m => m.id === assistantId)
            if (existing) return prev.map(m => (m.id === assistantId ? { ...m, content: m.content + text } : m))
            return [...prev, { id: assistantId, role: 'assistant', content: text, at: Date.now(), pending: true }]
          })
          setSending(false)
          setStreaming(true)
        } else if (p.kind === 'done') {
          const reply: string | undefined = p.reply
          setMessages(prev => {
            const existing = prev.find(m => m.id === assistantId)
            if (existing) {
              return prev.map(m =>
                m.id === assistantId ? { ...m, content: reply || m.content, pending: false } : m
              )
            }
            return [...prev, { id: assistantId, role: 'assistant', content: reply ?? '', at: Date.now() }]
          })
          finalizeAssistant(reply ?? '')
        }
      } else if (data.type === 'oneai:assistant-message') {
        // Non-streaming fallback path. If a streaming stub already exists for
        // this turn (stream died mid-way), replace it instead of duplicating.
        const reply: string = data.payload?.reply ?? ''
        const clientId: string | undefined = data.payload?.clientId
        const assistantId = clientId ? assistantIdFor(clientId) : null
        setMessages(prev => {
          if (assistantId && prev.some(m => m.id === assistantId)) {
            return prev.map(m => (m.id === assistantId ? { ...m, content: reply, pending: false } : m))
          }
          return [...prev, { id: assistantId ?? generateMessageId(), role: 'assistant', content: reply, at: Date.now() }]
        })
        finalizeAssistant(reply)
      } else if (data.type === 'oneai:history') {
        // Returning-visitor transcript. Only hydrate an untouched chat (just
        // the greeting) -- never clobber a conversation already in progress.
        const history: Array<{ role: 'user' | 'assistant'; content: string; at?: string | null }> =
          data.payload?.messages ?? []
        if (history.length) {
          setMessages(prev => {
            if (prev.length > 1) return prev
            const restored: ChatMessage[] = history.map((m, i) => ({
              id: `history-${i}`,
              role: m.role,
              content: m.content,
              at: m.at ? new Date(m.at).getTime() || Date.now() : Date.now(),
            }))
            return [...prev.slice(0, 1), ...restored]
          })
        }
      } else if (data.type === 'oneai:assistant-status') {
        const text: string | undefined = data.payload?.text
        if (text) setStatusText(text)
      } else if (data.type === 'oneai:send-failed') {
        const clientId: string | undefined = data.payload?.clientId
        setMessages(prev =>
          prev
            .filter(m => !(clientId && m.id === assistantIdFor(clientId) && m.pending))
            .map(m => (clientId && m.id === clientId ? { ...m, failed: true } : m))
        )
        setSending(false)
        setStreaming(false)
        setStatusText(null)
      } else if (data.type === 'oneai:connection') {
        setOnline(data.payload?.online !== false)
      } else if (data.type === 'oneai:upload-result') {
        const p = data.payload ?? {}
        setPendingAttachments(prev =>
          prev.map(a =>
            a.uploadId === p.uploadId
              ? p.ok
                ? { ...a, status: 'ready', ref: p.attachment ?? {} }
                : { ...a, status: 'error' }
              : a
          )
        )
        if (p.ok === false) setAttachmentError(p.message || 'Upload failed.')
      } else if (data.type === 'oneai:visibility') {
        if (data.payload?.open) textareaRef.current?.focus()
      } else if (data.type === 'oneai:lead-ack') {
        setLeadSubmitted(true)
      } else if (data.type === 'oneai:error') {
        setMessages(prev => [...prev, { id: generateMessageId(), role: 'assistant', content: data.payload?.message || branding.error_message_text, at: Date.now() }])
        setSending(false)
        setStreaming(false)
        setStatusText(null)
      }
    }

    window.addEventListener('message', handleMessage)
    // Tell the parent we're mounted and ready to receive branding/greeting.
    window.parent.postMessage({ type: 'oneai:ready' }, '*')
    return () => window.removeEventListener('message', handleMessage)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Escape anywhere inside the iframe closes (minimizes) the widget.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') window.parent.postMessage({ type: 'oneai:minimize' }, '*')
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // Admin-supplied custom CSS -- injected AFTER the built-in styles so it can
  // override them. Safe: this document is sandboxed inside the widget iframe,
  // so the CSS can never touch the host page.
  useEffect(() => {
    const css = branding.custom_css
    if (!css || !css.trim()) return
    const style = document.createElement('style')
    style.setAttribute('data-oneai-custom-css', '')
    style.textContent = css
    document.head.appendChild(style)
    return () => { document.head.removeChild(style) }
  }, [branding.custom_css])

  // Auto-scroll only while the visitor is already at (or near) the bottom.
  // If they scrolled up to reread something, new content must not yank them
  // down -- a "new messages" pill appears instead.
  const atBottomRef = useRef(true)
  const [showJumpPill, setShowJumpPill] = useState(false)

  const [copiedId, setCopiedId] = useState<string | null>(null)
  const handleCopy = async (m: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(m.content)
      setCopiedId(m.id)
      setTimeout(() => setCopiedId(null), 1500)
    } catch { /* clipboard unavailable */ }
  }

  const handleLogScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48
    atBottomRef.current = atBottom
    if (atBottom) setShowJumpPill(false)
  }

  const scrollToBottom = (smooth = true) => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: smooth && !accessibility.reduced_motion ? 'smooth' : 'auto',
    })
    atBottomRef.current = true
    setShowJumpPill(false)
  }

  useEffect(() => {
    if (atBottomRef.current) scrollToBottom()
    else setShowJumpPill(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, sending])

  const autoGrow = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, TEXTAREA_MAX_HEIGHT)}px`
  }

  const postSend = (clientId: string, text: string, attachments?: AttachmentRef[]) => {
    setStatusText(null)
    window.parent.postMessage(
      { type: 'oneai:send-message', payload: { text, clientId, attachments: attachments?.length ? attachments : undefined } },
      '*'
    )
  }

  const sendText = (text: string) => {
    if (!text || sending || streaming) return
    if (pendingAttachments.some(a => a.status === 'uploading')) return
    const clientId = generateMessageId()
    const attachments = pendingAttachments.filter(a => a.status === 'ready' && a.ref).map(a => a.ref as AttachmentRef)
    setMessages(prev => [...prev, { id: clientId, role: 'user', content: text, at: Date.now(), attachments: attachments.length ? attachments : undefined }])
    setInput('')
    setPendingAttachments([])
    setAttachmentError(null)
    setSending(true)
    postSend(clientId, text, attachments)
    requestAnimationFrame(autoGrow)
  }

  const retryMessage = (message: ChatMessage) => {
    if (sending || streaming) return
    setMessages(prev => prev.map(m => (m.id === message.id ? { ...m, failed: false, at: Date.now() } : m)))
    setSending(true)
    postSend(message.id, message.content, message.attachments)
  }

  const handleFilePick = (file: File | null) => {
    if (!file) return
    setAttachmentError(null)
    if (pendingAttachments.length >= MAX_ATTACHMENTS) {
      setAttachmentError(`You can attach up to ${MAX_ATTACHMENTS} files.`)
      return
    }
    if (file.size > MAX_ATTACHMENT_BYTES) {
      setAttachmentError('File is too large (max 10MB).')
      return
    }
    const uploadId = generateMessageId()
    setPendingAttachments(prev => [...prev, { uploadId, name: file.name, status: 'uploading' }])
    // The parent owns ALL network calls (its origin is what the backend's
    // allowlist checks) -- so the File itself crosses via postMessage
    // (File objects are structured-cloneable) and the parent uploads it.
    window.parent.postMessage({ type: 'oneai:upload-request', payload: { uploadId, file } }, '*')
  }

  const removeAttachment = (uploadId: string) => {
    setPendingAttachments(prev => prev.filter(a => a.uploadId !== uploadId))
  }

  const handleFeedback = (message: ChatMessage, rating: 'up' | 'down') => {
    if (feedback[message.id] === rating) return
    setFeedback(prev => ({ ...prev, [message.id]: rating }))
    window.parent.postMessage(
      { type: 'oneai:feedback', payload: { messageId: message.id, rating, excerpt: message.content.slice(0, 500) } },
      '*'
    )
  }

  const handleMinimize = () => {
    window.parent.postMessage({ type: 'oneai:minimize' }, '*')
  }

  const handleLeadSubmit = () => {
    const missing = leadFields.some(f => f.required && !leadValues[f.field_name]?.trim())
    if (missing) return
    window.parent.postMessage({ type: 'oneai:lead-submit', payload: { values: leadValues } }, '*')
    setLeadSubmitted(true)
  }

  if (!ready) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-white">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-200 border-t-violet-600" />
      </div>
    )
  }

  const colors = deriveWidgetColors(branding)
  const bubbleRadius = bubbleRadiusFor(layout.bubble_style)
  const spacing = spacingFor(layout.spacing_density)
  const large = accessibility.large_text
  const noMotion = accessibility.reduced_motion
  const available = isCurrentlyAvailable(availability)
  const showLeadForm = leadFields.length > 0 && !leadSubmitted
  const showAvatars = branding.show_avatars_in_messages
  const showTimestamps = branding.show_timestamps
  const textDirection: WidgetTextDirection = branding.text_direction ?? 'auto'
  const ui = uiStringsFor(locale)
  const localeIsRtl = RTL_LANGUAGES.has((locale ?? '').toLowerCase().split('-')[0])
  // Explicit ltr/rtl flips the whole chat root (the flex justify-* +
  // text-start/end classes below mirror with it automatically). 'auto' flips
  // the root only when the visitor's locale is an RTL language; individual
  // bubbles/textarea still resolve their own direction via dir="auto".
  const rootDir = textDirection === 'auto' ? (localeIsRtl ? ('rtl' as const) : undefined) : textDirection
  const autoDir = textDirection === 'auto' ? ('auto' as const) : undefined
  const userBubbleText = readableTextOn(colors.userBubbleBg)
  const sendIconColor = readableTextOn(colors.sendButtonBg)
  const showTyping = sending && !streaming
  const uploading = pendingAttachments.some(a => a.status === 'uploading')

  return (
    <div
      dir={rootDir}
      className="flex h-screen w-screen flex-col overflow-hidden"
      style={{
        backgroundColor: colors.bg,
        color: colors.text,
        fontFamily: branding.font_family,
        fontSize: branding.font_size_base,
        fontWeight: branding.font_weight === 'bold' ? 700 : branding.font_weight === 'medium' ? 500 : 400,
        filter: accessibility.high_contrast ? 'contrast(1.3)' : undefined,
      }}
    >
      {!noMotion && (
        <style>{`
          @keyframes oneai-msg-in {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
          }
          .oneai-msg-in { animation: oneai-msg-in 150ms ease-out; }
        `}</style>
      )}
      {/* Screen-reader announcement of new assistant replies. */}
      <div aria-live="polite" className="sr-only">{announcement}</div>
      <div
        className="flex items-center justify-between px-4 py-3 shrink-0 border-b"
        style={{ backgroundColor: colors.headerBg, color: colors.headerText, borderColor: colors.borderColor }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {branding.header_logo_url || branding.assistant_avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={branding.header_logo_url || branding.assistant_avatar_url || ''} alt="" className="w-8 h-8 rounded-lg object-cover shrink-0" />
          ) : (
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white shrink-0"
              style={{ background: avatarTileBackground(branding) }}
            >
              <Sparkles className="w-4 h-4" />
            </div>
          )}
          <div className="min-w-0">
            <p className={`font-semibold truncate leading-tight ${large ? 'text-[16px]' : 'text-[14px]'}`}>{branding.header_title}</p>
            {branding.header_subtitle ? (
              <p className={`truncate opacity-70 ${large ? 'text-[12px]' : 'text-[11px]'}`}>{branding.header_subtitle}</p>
            ) : (
              <div className="flex items-center gap-1 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: available ? '#10b981' : '#9ca3af' }} />
                <span className={`font-medium ${large ? 'text-[12px]' : 'text-[11px]'}`} style={{ color: available ? '#10b981' : undefined, opacity: available ? 1 : 0.6 }}>
                  {available ? ui.online : ui.away}
                </span>
              </div>
            )}
          </div>
        </div>
        <button onClick={handleMinimize} aria-label="Minimize" className="opacity-70 hover:opacity-100 shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      {!online && (
        <div
          role="status"
          className={`px-4 py-2 shrink-0 ${large ? 'text-[13px]' : 'text-[11px]'}`}
          style={{ backgroundColor: '#FEF3C7', color: '#92400E' }}
        >
          You&apos;re offline — messages will send when you&apos;re back.
        </div>
      )}

      {!available && (
        <div
          className={`px-4 py-2 shrink-0 ${large ? 'text-[13px]' : 'text-[11px]'}`}
          style={{ backgroundColor: colors.subtleBg, color: colors.text }}
        >
          {availability?.offline_message || "We're offline right now. Leave a message and we'll get back to you."}
        </div>
      )}

      {showLeadForm ? (
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          <p className={`${large ? 'text-[15px]' : 'text-[13px]'}`}>{branding.greeting_message}</p>
          {leadFields.map(field => (
            <div key={field.field_name}>
              <label className={`block mb-1 ${large ? 'text-[13px]' : 'text-[11px]'}`} style={{ color: colors.text }}>
                {field.label}{field.required ? ' *' : ''}
              </label>
              <input
                type={field.field_type === 'email' ? 'email' : field.field_type === 'phone' ? 'tel' : 'text'}
                value={leadValues[field.field_name] ?? ''}
                onChange={e => setLeadValues(prev => ({ ...prev, [field.field_name]: e.target.value }))}
                className={`w-full rounded-lg px-3 py-2 outline-none border ${large ? 'text-[14px]' : 'text-[12px]'}`}
                style={{ backgroundColor: colors.subtleBg, color: colors.text, borderColor: colors.borderColor }}
              />
            </div>
          ))}
          <button
            onClick={handleLeadSubmit}
            className={`w-full rounded-full py-2 font-medium ${large ? 'text-[14px]' : 'text-[12px]'} ${noMotion ? '' : 'transition-opacity hover:opacity-90'}`}
            style={{ backgroundColor: branding.theme_color, color: readableTextOn(branding.theme_color) }}
          >
            {ui.continue_}
          </button>
        </div>
      ) : (
        <>
          <div
            ref={scrollRef}
            role="log"
            aria-label="Chat messages"
            onScroll={handleLogScroll}
            className="flex-1 overflow-y-auto px-3 relative"
            style={{ paddingTop: spacing.padY, paddingBottom: spacing.padY, display: 'flex', flexDirection: 'column', gap: spacing.gap }}
          >
            {messages.map((m, i) => {
              const avatarUrl = m.role === 'user' ? branding.user_avatar_url : branding.assistant_avatar_url
              // Avatar only on the first message of a consecutive same-role
              // run; an invisible spacer keeps grouped bubbles aligned.
              const firstOfGroup = i === 0 || messages[i - 1].role !== m.role
              return (
                <div key={m.id} className={`flex items-end gap-2 ${noMotion ? '' : 'oneai-msg-in'} ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {showAvatars && m.role === 'assistant' && avatarUrl && (
                    firstOfGroup ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={avatarUrl} alt="" className="w-6 h-6 rounded-full object-cover shrink-0" />
                    ) : (
                      <span className="w-6 shrink-0" aria-hidden="true" />
                    )
                  )}
                  <div className="max-w-[80%]">
                    <div
                      dir={autoDir}
                      className={`leading-relaxed break-words ${m.role === 'user' ? 'whitespace-pre-wrap' : ''} ${large ? 'text-[15px]' : 'text-[13px]'}`}
                      style={{
                        borderRadius: bubbleRadius,
                        paddingLeft: spacing.padX,
                        paddingRight: spacing.padX,
                        paddingTop: spacing.padY,
                        paddingBottom: spacing.padY,
                        backgroundColor: m.role === 'user' ? colors.userBubbleBg : colors.assistantBubbleBg,
                        color: m.role === 'user' ? userBubbleText : colors.text,
                        opacity: m.failed ? 0.65 : 1,
                      }}
                    >
                      {m.role === 'user' && m.attachments && m.attachments.length > 0 && (
                        <span className="flex flex-wrap gap-1 mb-1">
                          {m.attachments.map((a, ai) => (
                            <span
                              key={ai}
                              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] bg-black/15"
                            >
                              <Paperclip className="w-2.5 h-2.5 shrink-0" />
                              <span className="max-w-[140px] truncate">{a.filename || a.url?.split('/').pop() || 'attachment'}</span>
                            </span>
                          ))}
                        </span>
                      )}
                      {m.role === 'assistant' ? (
                        m.pending ? (
                          // Plain text while streaming: re-parsing markdown on
                          // every token makes tables/code jump around; the
                          // finalized message gets the full rich render.
                          <span className="whitespace-pre-wrap">{m.content}</span>
                        ) : (
                          <WidgetRichContent
                            content={m.content}
                            themeColor={branding.theme_color}
                            onSend={sendText}
                            disabled={sending || streaming}
                            large={large}
                          />
                        )
                      ) : (
                        m.content
                      )}
                    </div>
                    {m.failed && (
                      <button
                        onClick={() => retryMessage(m)}
                        className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-red-500 hover:text-red-600"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Not sent — Retry
                      </button>
                    )}
                    {showTimestamps && !m.failed && (
                      <p className={`mt-1 opacity-60 ${large ? 'text-[11px]' : 'text-[10px]'} ${m.role === 'user' ? 'text-end' : 'text-start'}`}>
                        {formatTime(m.at)}
                      </p>
                    )}
                    {m.role === 'assistant' && i > 0 && !m.pending && (
                      <div className="flex items-center gap-1 mt-1">
                        <button
                          onClick={() => handleFeedback(m, 'up')}
                          aria-label="Good response"
                          className="p-1 rounded opacity-50 hover:opacity-100 transition-opacity"
                          style={feedback[m.id] === 'up' ? { color: '#10b981', opacity: 1 } : undefined}
                        >
                          <ThumbsUp className="w-3 h-3" fill={feedback[m.id] === 'up' ? 'currentColor' : 'none'} />
                        </button>
                        <button
                          onClick={() => handleFeedback(m, 'down')}
                          aria-label="Bad response"
                          className="p-1 rounded opacity-50 hover:opacity-100 transition-opacity"
                          style={feedback[m.id] === 'down' ? { color: '#ef4444', opacity: 1 } : undefined}
                        >
                          <ThumbsDown className="w-3 h-3" fill={feedback[m.id] === 'down' ? 'currentColor' : 'none'} />
                        </button>
                        <button
                          onClick={() => handleCopy(m)}
                          aria-label="Copy reply"
                          className="p-1 rounded opacity-50 hover:opacity-100 transition-opacity"
                          style={copiedId === m.id ? { color: '#10b981', opacity: 1 } : undefined}
                        >
                          {copiedId === m.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        </button>
                      </div>
                    )}
                  </div>
                  {showAvatars && m.role === 'user' && avatarUrl && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={avatarUrl} alt="" className="w-6 h-6 rounded-full object-cover shrink-0" />
                  )}
                </div>
              )
            })}
            {messages.length === 1 && branding.quick_replies.length > 0 && (
              <div className="flex flex-wrap gap-2 ps-1">
                {branding.quick_replies.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => sendText(q)}
                    className={`rounded-full px-3 py-1.5 border ${large ? 'text-[13px]' : 'text-[11.5px]'} ${noMotion ? '' : 'transition-colors hover:bg-black/5 dark:hover:bg-white/5'}`}
                    style={{ borderColor: branding.theme_color, color: branding.theme_color }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
            {showTyping && (
              <div className="flex justify-start">
                <div
                  className="flex items-center gap-2 text-[13px]"
                  style={{ borderRadius: bubbleRadius, padding: `${spacing.padY}px ${spacing.padX}px`, backgroundColor: colors.assistantBubbleBg, color: colors.text }}
                >
                  <span>{statusText ?? branding.loading_text}</span>
                  <span className="inline-flex gap-1">
                    <span className={`w-1.5 h-1.5 rounded-full bg-current opacity-40 ${noMotion ? '' : 'animate-bounce [animation-delay:-0.3s]'}`} />
                    <span className={`w-1.5 h-1.5 rounded-full bg-current opacity-40 ${noMotion ? '' : 'animate-bounce [animation-delay:-0.15s]'}`} />
                    <span className={`w-1.5 h-1.5 rounded-full bg-current opacity-40 ${noMotion ? '' : 'animate-bounce'}`} />
                  </span>
                </div>
              </div>
            )}
          </div>

          {showJumpPill && (
            <div className="relative">
              <button
                type="button"
                onClick={() => scrollToBottom()}
                className={`absolute -top-10 start-1/2 -translate-x-1/2 z-10 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 shadow-md font-medium ${large ? 'text-[12.5px]' : 'text-[11.5px]'} ${noMotion ? '' : 'oneai-msg-in'}`}
                style={{ backgroundColor: branding.theme_color, color: readableTextOn(branding.theme_color) }}
              >
                <ArrowDown className="w-3 h-3" />
                New messages
              </button>
            </div>
          )}
          <div className="px-3 pb-3 pt-2 shrink-0 border-t" style={{ borderColor: colors.borderColor }}>
            {(pendingAttachments.length > 0 || attachmentError) && (
              <div className="flex flex-wrap items-center gap-1.5 mb-2">
                {pendingAttachments.map(a => (
                  <span
                    key={a.uploadId}
                    className="inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px]"
                    style={{
                      borderColor: a.status === 'error' ? '#ef4444' : colors.borderColor,
                      backgroundColor: colors.subtleBg,
                      color: a.status === 'error' ? '#ef4444' : colors.text,
                      opacity: a.status === 'uploading' ? 0.7 : 1,
                    }}
                  >
                    {a.status === 'uploading' ? (
                      <span className="w-3 h-3 shrink-0 animate-spin rounded-full border border-current border-t-transparent" />
                    ) : (
                      <Paperclip className="w-3 h-3 shrink-0" />
                    )}
                    <span className="max-w-[140px] truncate">{a.name}</span>
                    <button onClick={() => removeAttachment(a.uploadId)} aria-label={`Remove ${a.name}`} className="opacity-60 hover:opacity-100">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {attachmentError && <span className="text-[11px] text-red-500">{attachmentError}</span>}
              </div>
            )}
            <div
              className="flex items-end gap-2 px-3 py-2.5 rounded-xl border"
              style={{ backgroundColor: colors.subtleBg, borderColor: colors.borderColor }}
            >
              {allowAttachments && (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ATTACHMENT_ACCEPT}
                    className="hidden"
                    onChange={e => {
                      handleFilePick(e.target.files?.[0] ?? null)
                      e.target.value = ''
                    }}
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={sending || pendingAttachments.length >= MAX_ATTACHMENTS}
                    aria-label="Attach a file"
                    className="shrink-0 flex items-center justify-center w-7 h-8 opacity-60 hover:opacity-100 disabled:opacity-30 transition-opacity"
                    style={{ color: colors.text }}
                  >
                    <Paperclip className="w-4 h-4" />
                  </button>
                </>
              )}
              <textarea
                ref={textareaRef}
                dir={autoDir}
                rows={1}
                value={input}
                onChange={e => { setInput(e.target.value); autoGrow() }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendText(input.trim())
                  }
                }}
                placeholder={branding.input_placeholder}
                disabled={sending}
                className={`flex-1 bg-transparent outline-none min-w-0 resize-none leading-relaxed ${large ? 'text-[14px]' : 'text-[13px]'}`}
                style={{ color: colors.text, maxHeight: TEXTAREA_MAX_HEIGHT }}
              />
              <button
                onClick={() => sendText(input.trim())}
                disabled={sending || uploading || !input.trim()}
                className="shrink-0 flex items-center justify-center w-8 h-8 disabled:opacity-40 transition-opacity"
                style={{ backgroundColor: colors.sendButtonBg, color: sendIconColor, borderRadius: sendButtonBorderRadius(layout.send_button_shape) }}
                aria-label="Send"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            </div>
            <p className="text-center mt-2 text-[10.5px] opacity-50">
              <kbd className="font-mono px-1 py-px rounded border" style={{ borderColor: colors.borderColor }}>Enter</kbd> {ui.enterHint}
              {' · '}
              <kbd className="font-mono px-1 py-px rounded border" style={{ borderColor: colors.borderColor }}>Shift+Enter</kbd> {ui.newline}
            </p>
          </div>
          {branding.show_branding && (
            <p className="text-center py-1.5 text-[10px] shrink-0 opacity-60">
              Powered by One-AI
            </p>
          )}
        </>
      )}
    </div>
  )
}
