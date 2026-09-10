'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Monitor, Moon, Smartphone, Sparkles, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import type { WidgetAvailabilityInput, WidgetBranding, WidgetLayout } from '@/types'
import {
  LAUNCHER_ICON_SVG,
  avatarTileBackground,
  bubbleRadiusFor,
  contrastRatioWithWhite,
  deriveWidgetColors,
  launcherBorderRadius,
  launcherShadowFor,
  readableTextOn,
  sendButtonBorderRadius,
  shadowFor,
  spacingFor,
} from '@/lib/widget-styles'

interface WidgetLivePreviewProps {
  branding: WidgetBranding
  layout: WidgetLayout
  /** When business hours are enabled, the preview header offers an
   * Online/Offline toggle so admins can see the offline banner. */
  availability?: WidgetAvailabilityInput
  /** Click-to-edit: clicking a region of the mock jumps to the tab that
   * configures it (header/messages/input -> appearance, launcher -> launcher). */
  onNavigate?: (target: 'appearance' | 'launcher') => void
}

const DEMO_MESSAGES = [
  { role: 'assistant' as const, content: null }, // filled from branding.greeting_message
  { role: 'user' as const, content: 'Do you offer a free trial?' },
  { role: 'assistant' as const, content: "Yes! Every plan starts with a 14-day free trial, no card required." },
]

const ANIMATION_MS = 220

/** Hidden-state transform/opacity for each configured open/close animation. */
function closedStyleFor(style: WidgetLayout['animation_style']): React.CSSProperties {
  switch (style) {
    case 'fade':
      return { opacity: 0 }
    case 'slide':
      return { opacity: 0, transform: 'translateY(16px)' }
    case 'scale':
      return { opacity: 0, transform: 'scale(0.92)' }
    default:
      return {}
  }
}

/**
 * Pure, local-state mock of the embedded chat surface -- never calls the
 * network. Mounted beside the Appearance/Layout tabs so every field change
 * is visible instantly. Shares style derivation with the real embed page
 * (lib/widget-styles.ts) so this can't visually drift from production.
 */
export function WidgetLivePreview({ branding, layout, availability, onNavigate }: WidgetLivePreviewProps) {
  // Hover affordance for the click-to-edit regions below.
  const editableProps = (target: 'appearance' | 'launcher', label: string) =>
    onNavigate
      ? {
          onClick: (e: React.MouseEvent) => { e.stopPropagation(); onNavigate(target) },
          title: `Edit ${label}`,
          className: 'cursor-pointer transition-shadow hover:ring-2 hover:ring-violet-400/60 hover:ring-inset',
        }
      : { className: '' }

  const [open, setOpen] = useState(true)
  // Kept mounted for one exit-animation cycle so close animates too.
  const [rendered, setRendered] = useState(true)
  const [entered, setEntered] = useState(true)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [viewport, setViewport] = useState<'desktop' | 'mobile'>('desktop')
  const [offlineView, setOfflineView] = useState(false)

  const colors = deriveWidgetColors(branding)
  const bubbleRadius = bubbleRadiusFor(layout.bubble_style)
  const spacing = spacingFor(layout.spacing_density)
  const launcherRadius = launcherBorderRadius(layout.launcher_shape, layout.launcher_size)
  const isMobile = viewport === 'mobile'
  const mobileFullScreen = isMobile && layout.mobile_full_screen
  const isLeft = branding.position === 'bottom-left'
  const animate = layout.animation_style !== 'none'

  const userBubbleText = readableTextOn(colors.userBubbleBg)
  const sendIconColor = readableTextOn(colors.sendButtonBg)
  // Warn when white text on the brand color would fall below WCAG's 3:1
  // minimum -- the preview auto-switches to dark text, but content authored
  // assuming white (icons, screenshots) can still look washed out.
  const poorContrast = contrastRatioWithWhite(colors.userBubbleBg) < 3
  const dir = branding.text_direction && branding.text_direction !== 'auto' ? branding.text_direction : undefined

  const availabilityEnabled = !!availability?.enabled
  const showOffline = availabilityEnabled && offlineView

  useEffect(() => () => { if (closeTimer.current) clearTimeout(closeTimer.current) }, [])

  const toggleOpen = () => {
    if (closeTimer.current) { clearTimeout(closeTimer.current); closeTimer.current = null }
    if (open) {
      setOpen(false)
      if (animate) {
        setEntered(false)
        closeTimer.current = setTimeout(() => setRendered(false), ANIMATION_MS)
      } else {
        setEntered(false)
        setRendered(false)
      }
    } else {
      setOpen(true)
      setRendered(true)
      if (animate) {
        // Mount hidden, then flip to the entered state on the next frame so
        // the transition actually plays.
        setEntered(false)
        requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)))
      } else {
        setEntered(true)
      }
    }
  }

  const iconSvg =
    layout.launcher_icon === 'custom'
      ? null
      : LAUNCHER_ICON_SVG[layout.launcher_icon] ?? LAUNCHER_ICON_SVG.chat

  const lastAssistantIndex = DEMO_MESSAGES.reduce((acc, m, i) => (m.role === 'assistant' ? i : acc), -1)

  return (
    <div className="sticky top-6">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[12px] font-medium text-[var(--text-3)]">Live preview</p>
        <div className="flex items-center gap-1.5">
          {availabilityEnabled && (
            <button
              type="button"
              onClick={() => setOfflineView(v => !v)}
              title="Toggle between the online and offline (outside business hours) views"
              className={`flex items-center gap-1 px-2 h-6 rounded-full border text-[11px] font-medium transition-colors ${
                offlineView
                  ? 'border-amber-400 bg-amber-500/10 text-amber-600 dark:text-amber-400'
                  : 'border-[var(--border)] text-[var(--text-3)] hover:text-[var(--text-1)]'
              }`}
            >
              <Moon className="w-3 h-3" />
              {offlineView ? 'Offline view' : 'Online view'}
            </button>
          )}
          <div className="flex items-center rounded-lg border border-[var(--border)] p-0.5">
            <button
              type="button"
              onClick={() => setViewport('desktop')}
              title="Desktop preview"
              className={`flex items-center justify-center w-6 h-6 rounded-[5px] transition-colors ${
                viewport === 'desktop' ? 'bg-violet-500/15 text-violet-600 dark:text-violet-400' : 'text-[var(--text-3)] hover:text-[var(--text-1)]'
              }`}
            >
              <Monitor className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setViewport('mobile')}
              title="Mobile preview"
              className={`flex items-center justify-center w-6 h-6 rounded-[5px] transition-colors ${
                viewport === 'mobile' ? 'bg-violet-500/15 text-violet-600 dark:text-violet-400' : 'text-[var(--text-3)] hover:text-[var(--text-1)]'
              }`}
            >
              <Smartphone className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
      <div
        className="relative rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)] overflow-hidden mx-auto transition-[width] duration-200"
        style={{ height: 640, width: isMobile ? 300 : '100%' }}
      >
        {rendered ? (
          <div
            dir={dir}
            className="absolute overflow-hidden flex flex-col"
            style={{
              ...(mobileFullScreen
                ? { inset: 0, width: '100%', height: '100%', borderRadius: 0 }
                : {
                    width: Math.min(layout.widget_width, isMobile ? 260 : 340),
                    height: Math.min(layout.widget_height, 560),
                    minWidth: layout.widget_min_width,
                    maxWidth: layout.widget_max_width,
                    minHeight: layout.widget_min_height,
                    maxHeight: layout.widget_max_height,
                    ...(isLeft ? { left: layout.offset_x } : { right: layout.offset_x }),
                    bottom: layout.offset_y + layout.launcher_size + 16,
                    borderRadius: layout.border_radius,
                    boxShadow: shadowFor(layout.shadow_style),
                  }),
              backgroundColor: colors.bg,
              color: colors.text,
              fontFamily: branding.font_family,
              fontSize: branding.font_size_base,
              fontWeight: branding.font_weight === 'bold' ? 700 : branding.font_weight === 'medium' ? 500 : 400,
              ...(animate
                ? {
                    transition: `opacity ${ANIMATION_MS}ms ease, transform ${ANIMATION_MS}ms cubic-bezier(0.16,1,0.3,1)`,
                    ...(entered ? { opacity: 1, transform: 'none' } : closedStyleFor(layout.animation_style)),
                  }
                : {}),
            }}
          >
            <div
              {...editableProps('appearance', 'header (Appearance tab)')}
              className={`flex items-center justify-between px-4 py-3 shrink-0 border-b ${editableProps('appearance', '').className}`}
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
                  <p className="font-semibold truncate leading-tight text-[14px]">{branding.header_title}</p>
                  {showOffline ? (
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: '#f59e0b' }} />
                      <span className="text-[11px] font-medium" style={{ color: '#f59e0b' }}>Offline</span>
                    </div>
                  ) : branding.header_subtitle ? (
                    <p className="truncate text-[11px] opacity-70">{branding.header_subtitle}</p>
                  ) : (
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: '#10b981' }} />
                      <span className="text-[11px] font-medium" style={{ color: '#10b981' }}>Online</span>
                    </div>
                  )}
                </div>
              </div>
              <button aria-label="Minimize" className="opacity-70 hover:opacity-100">
                <X className="w-4 h-4" />
              </button>
            </div>

            {showOffline && (
              <div
                className="shrink-0 px-4 py-2 text-[12px] border-b"
                style={{
                  backgroundColor: 'rgba(245, 158, 11, 0.12)',
                  color: branding.dark_mode ? '#fbbf24' : '#b45309',
                  borderColor: colors.borderColor,
                }}
              >
                {availability?.offline_message || "We're offline right now. Leave a message and we'll get back to you."}
              </div>
            )}

            <div
              {...editableProps('appearance', 'messages & copy (Appearance tab)')}
              className={`flex-1 overflow-y-auto px-3 ${editableProps('appearance', '').className}`}
              style={{ paddingTop: spacing.padY, paddingBottom: spacing.padY, display: 'flex', flexDirection: 'column', gap: spacing.gap }}
            >
              {DEMO_MESSAGES.map((m, i) => {
                const content = m.content ?? branding.greeting_message
                const showAvatar = branding.show_avatars_in_messages
                const avatarUrl = m.role === 'user' ? branding.user_avatar_url : branding.assistant_avatar_url
                const isLastAssistant = i === lastAssistantIndex
                return (
                  <div key={i} className={`flex items-end gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {showAvatar && m.role === 'assistant' && avatarUrl && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={avatarUrl} alt="" className="w-6 h-6 rounded-full object-cover shrink-0" />
                    )}
                    <div>
                      <div
                        className="max-w-[220px] leading-relaxed whitespace-pre-wrap break-words text-[13px]"
                        style={{
                          borderRadius: bubbleRadius,
                          paddingLeft: spacing.padX,
                          paddingRight: spacing.padX,
                          paddingTop: spacing.padY,
                          paddingBottom: spacing.padY,
                          backgroundColor: m.role === 'user' ? colors.userBubbleBg : colors.assistantBubbleBg,
                          color: m.role === 'user' ? userBubbleText : colors.text,
                        }}
                      >
                        {content}
                      </div>
                      {branding.show_timestamps && (
                        <p className={`text-[10px] mt-1 opacity-60 ${m.role === 'user' ? 'text-right' : 'text-left'}`}>
                          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      )}
                      {isLastAssistant && (
                        <div className="flex items-center gap-1.5 mt-1.5 pl-1 opacity-60">
                          <ThumbsUp className="w-3 h-3" style={{ color: colors.text }} />
                          <ThumbsDown className="w-3 h-3" style={{ color: colors.text }} />
                        </div>
                      )}
                    </div>
                    {showAvatar && m.role === 'user' && avatarUrl && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={avatarUrl} alt="" className="w-6 h-6 rounded-full object-cover shrink-0" />
                    )}
                  </div>
                )
              })}

              {/* Typing indicator, always shown so admins see the loading state. */}
              <div className="flex items-end gap-2 justify-start">
                <div
                  className="flex items-center gap-1.5"
                  style={{
                    borderRadius: bubbleRadius,
                    paddingLeft: spacing.padX,
                    paddingRight: spacing.padX,
                    paddingTop: spacing.padY,
                    paddingBottom: spacing.padY,
                    backgroundColor: colors.assistantBubbleBg,
                  }}
                >
                  {[0, 1, 2].map(d => (
                    <span
                      key={d}
                      className="w-1.5 h-1.5 rounded-full animate-pulse"
                      style={{ backgroundColor: colors.text, opacity: 0.5, animationDelay: `${d * 160}ms` }}
                    />
                  ))}
                  {branding.loading_text && (
                    <span className="text-[11px] opacity-60 ml-1" style={{ color: colors.text }}>{branding.loading_text}</span>
                  )}
                </div>
              </div>

              {branding.quick_replies.length > 0 && (
                <div className="flex flex-wrap gap-2 pl-1">
                  {branding.quick_replies.slice(0, 3).map((q, i) => (
                    <span
                      key={i}
                      className="rounded-full px-3 py-1.5 border text-[11.5px]"
                      style={{ borderColor: branding.theme_color, color: branding.theme_color }}
                    >
                      {q}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div
              {...editableProps('appearance', 'input & send button (Appearance tab)')}
              className={`px-3 pb-3 pt-2 shrink-0 border-t ${editableProps('appearance', '').className}`}
              style={{ borderColor: colors.borderColor }}
            >
              <div
                className="flex items-end gap-2 px-3 py-2.5 rounded-xl border"
                style={{ backgroundColor: colors.subtleBg, borderColor: colors.borderColor }}
              >
                <div className="flex-1 text-[13px] opacity-60" style={{ color: colors.text }}>
                  {branding.input_placeholder}
                </div>
                <div
                  className="shrink-0 flex items-center justify-center w-8 h-8"
                  style={{ backgroundColor: colors.sendButtonBg, color: sendIconColor, borderRadius: sendButtonBorderRadius(layout.send_button_shape) }}
                >
                  <ArrowUp className="w-4 h-4" />
                </div>
              </div>
              <p className="text-center mt-2 text-[10.5px] opacity-50">
                <kbd className="font-mono px-1 py-px rounded border" style={{ borderColor: colors.borderColor }}>Enter</kbd> to send
                {' · '}
                <kbd className="font-mono px-1 py-px rounded border" style={{ borderColor: colors.borderColor }}>Shift+Enter</kbd> for new line
              </p>
            </div>
            {branding.show_branding && (
              <p className="text-center py-1.5 text-[10px] shrink-0 opacity-60">Powered by One-AI</p>
            )}
          </div>
        ) : null}

        {!(mobileFullScreen && open) && (
          <button
            type="button"
            onClick={toggleOpen}
            aria-label="Toggle preview"
            className="absolute flex items-center justify-center"
            style={{
              width: layout.launcher_size,
              height: layout.launcher_size,
              ...(isLeft ? { left: layout.offset_x } : { right: layout.offset_x }),
              bottom: layout.offset_y,
              borderRadius: launcherRadius,
              backgroundColor: branding.theme_color,
              boxShadow: launcherShadowFor(layout.shadow_style),
            }}
          >
            {iconSvg ? (
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" dangerouslySetInnerHTML={{ __html: iconSvg }} />
            ) : layout.launcher_icon_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={layout.launcher_icon_url} alt="" className="w-6 h-6 object-contain" />
            ) : null}
          </button>
        )}
      </div>
      {poorContrast && (
        <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-2">
          Low contrast: white text on your visitor-bubble color is below 3:1, so the widget switches to dark
          text. Consider a darker brand color if you want white text.
        </p>
      )}
      <p className="text-[11px] text-[var(--text-3)] mt-2">
        {isMobile
          ? layout.mobile_full_screen
            ? 'Mobile preview — full-screen mode is on, so the chat fills the whole viewport below your configured breakpoint.'
            : 'Mobile preview — full-screen mode is off, so the chat keeps its windowed size even on small viewports.'
          : 'Mock preview — click the launcher to toggle.'}
      </p>
    </div>
  )
}
