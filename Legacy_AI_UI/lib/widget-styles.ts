import type { WidgetBranding, WidgetBrandingInput, WidgetLayout, WidgetLayoutInput } from '@/types'

/**
 * Pure style-derivation shared by the live admin preview (WidgetLivePreview)
 * and the real embedded widget (app/(embed)/embed/[widgetId]/page.tsx +
 * public/widget.js's inline styles) so the two surfaces can never visually
 * drift apart -- every value here is computed the same way in both places.
 */

/** Single source of truth for widget defaults, shared by WidgetCreateForm and
 * WidgetDetailView (both the initial-state and "reset to default" values). */
export const DEFAULT_WIDGET_BRANDING: WidgetBrandingInput = {
  theme_color: '#4F46E5',
  header_title: 'Chat with us',
  header_subtitle: '',
  header_logo_url: '',
  header_text_color: '#111827',
  header_bg_color: '',
  greeting_message: 'Hi! How can I help you today?',
  font_family: 'system-ui',
  font_size_base: 14,
  font_weight: 'normal',
  secondary_color: '#818CF8',
  background_color: '',
  text_color: '',
  border_color: '',
  assistant_avatar_url: '',
  user_avatar_url: '',
  show_avatars_in_messages: false,
  user_bubble_color: '',
  assistant_bubble_color: '',
  show_timestamps: false,
  input_placeholder: 'Type a message…',
  send_button_color: '',
  loading_text: 'Thinking…',
  empty_state_text: 'No messages yet. Say hello!',
  error_message_text: 'Something went wrong. Please try again.',
  dark_mode: false,
  quick_replies: [],
  show_branding: true,
}

export const DEFAULT_WIDGET_LAYOUT: WidgetLayoutInput = {
  widget_width: 380,
  widget_height: 600,
  widget_min_width: 300,
  widget_min_height: 400,
  widget_max_width: 480,
  widget_max_height: 760,
  launcher_size: 56,
  launcher_shape: 'circle',
  launcher_icon: 'chat',
  launcher_icon_url: '',
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

export interface WidgetThemePreset {
  key: string
  label: string
  /** Swatch shown in the picker -- the preset's primary + secondary color. */
  swatch: [string, string]
  branding: WidgetBrandingInput
}

/** Curated theme presets -- each is a full, self-consistent color set (not
 * just a primary color) so applying one never leaves mismatched header/bubble
 * colors behind. Only touches color/typography fields, never copy/layout. */
export const WIDGET_THEME_PRESETS: WidgetThemePreset[] = [
  {
    key: 'indigo',
    label: 'Indigo',
    swatch: ['#4F46E5', '#818CF8'],
    branding: {
      theme_color: '#4F46E5', secondary_color: '#818CF8', dark_mode: false,
      background_color: '', text_color: '', border_color: '',
      header_bg_color: '', header_text_color: '#111827',
      user_bubble_color: '', assistant_bubble_color: '', send_button_color: '',
    },
  },
  {
    key: 'midnight',
    label: 'Midnight',
    swatch: ['#818CF8', '#0F172A'],
    branding: {
      theme_color: '#818CF8', secondary_color: '#38BDF8', dark_mode: true,
      background_color: '#0F172A', text_color: '#E2E8F0', border_color: '#1E293B',
      header_bg_color: '#0F172A', header_text_color: '#E2E8F0',
      user_bubble_color: '', assistant_bubble_color: '', send_button_color: '',
    },
  },
  {
    key: 'slate',
    label: 'Slate',
    swatch: ['#334155', '#94A3B8'],
    branding: {
      theme_color: '#334155', secondary_color: '#94A3B8', dark_mode: false,
      background_color: '#ffffff', text_color: '#1E293B', border_color: '#E2E8F0',
      header_bg_color: '#F8FAFC', header_text_color: '#1E293B',
      user_bubble_color: '', assistant_bubble_color: '', send_button_color: '',
    },
  },
  {
    key: 'emerald',
    label: 'Emerald',
    swatch: ['#059669', '#6EE7B7'],
    branding: {
      theme_color: '#059669', secondary_color: '#34D399', dark_mode: false,
      background_color: '', text_color: '', border_color: '',
      header_bg_color: '', header_text_color: '#111827',
      user_bubble_color: '', assistant_bubble_color: '', send_button_color: '',
    },
  },
  {
    key: 'sunset',
    label: 'Sunset',
    swatch: ['#EA580C', '#FDBA74'],
    branding: {
      theme_color: '#EA580C', secondary_color: '#FB923C', dark_mode: false,
      background_color: '', text_color: '', border_color: '',
      header_bg_color: '', header_text_color: '#111827',
      user_bubble_color: '', assistant_bubble_color: '', send_button_color: '',
    },
  },
  {
    key: 'rose',
    label: 'Rose',
    swatch: ['#E11D48', '#FDA4AF'],
    branding: {
      theme_color: '#E11D48', secondary_color: '#FB7185', dark_mode: false,
      background_color: '', text_color: '', border_color: '',
      header_bg_color: '', header_text_color: '#111827',
      user_bubble_color: '', assistant_bubble_color: '', send_button_color: '',
    },
  },
]

/** Sentinel value the appearance form uses for the "Custom…" font option --
 * never persisted; it just reveals a free-text input. */
export const WIDGET_CUSTOM_FONT_VALUE = '__custom__'

/** Curated font stacks offered in the appearance form's font Select. Values
 * are real CSS font-family stacks persisted as-is to branding.font_family. */
export const WIDGET_FONT_STACKS: { value: string; label: string }[] = [
  { value: 'system-ui', label: 'System UI (default)' },
  { value: "Inter, system-ui, sans-serif", label: 'Inter' },
  { value: "Georgia, 'Times New Roman', serif", label: 'Georgia' },
  { value: "'Times New Roman', Times, serif", label: 'Times' },
  { value: 'Verdana, Geneva, sans-serif', label: 'Verdana' },
  { value: 'Tahoma, Geneva, sans-serif', label: 'Tahoma' },
  { value: "'Trebuchet MS', Helvetica, sans-serif", label: 'Trebuchet' },
  { value: "'Courier New', Courier, monospace", label: 'Courier (mono)' },
]

/** Matches the backend's color validation: #RGB, #RRGGBB, or #RRGGBBAA.
 * Empty/blank is also valid (means "auto / fall back"). */
export function isValidWidgetHexColor(value: string): boolean {
  const v = value.trim()
  if (!v) return true
  return /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(v)
}

const SHADOW_MAP: Record<WidgetLayout['shadow_style'], string> = {
  none: 'none',
  soft: '0 2px 10px rgba(0,0,0,0.12)',
  medium: '0 12px 40px rgba(0,0,0,0.25)',
  strong: '0 20px 60px rgba(0,0,0,0.4)',
}

const LAUNCHER_SHADOW_MAP: Record<WidgetLayout['shadow_style'], string> = {
  none: 'none',
  soft: '0 2px 8px rgba(0,0,0,0.15)',
  medium: '0 4px 16px rgba(0,0,0,0.2)',
  strong: '0 8px 28px rgba(0,0,0,0.35)',
}

const BUBBLE_RADIUS_MAP: Record<WidgetLayout['bubble_style'], number> = {
  rounded: 18,
  square: 4,
  soft: 8,
}

const SPACING_MAP: Record<WidgetLayout['spacing_density'], { gap: number; padY: number; padX: number }> = {
  compact: { gap: 8, padY: 6, padX: 10 },
  comfortable: { gap: 12, padY: 8, padX: 12 },
  spacious: { gap: 18, padY: 12, padX: 16 },
}

export function shadowFor(style: WidgetLayout['shadow_style']): string {
  return SHADOW_MAP[style] ?? SHADOW_MAP.medium
}

export function launcherShadowFor(style: WidgetLayout['shadow_style']): string {
  return LAUNCHER_SHADOW_MAP[style] ?? LAUNCHER_SHADOW_MAP.medium
}

export function bubbleRadiusFor(style: WidgetLayout['bubble_style']): number {
  return BUBBLE_RADIUS_MAP[style] ?? BUBBLE_RADIUS_MAP.rounded
}

export function spacingFor(density: WidgetLayout['spacing_density']) {
  return SPACING_MAP[density] ?? SPACING_MAP.comfortable
}

export function launcherBorderRadius(shape: WidgetLayout['launcher_shape'], size: number): number {
  return shape === 'circle' ? size / 2 : Math.min(16, size / 3.5)
}

export function sendButtonBorderRadius(shape: WidgetLayout['send_button_shape'], size = 36): number {
  if (shape === 'circle') return size / 2
  if (shape === 'square') return 8
  return 18
}

/** Small gradient tile shown in the header/preview when no logo/avatar image
 * is configured yet -- the default "brand mark" look, e.g. the Playground's
 * Supervisor tile. */
export function avatarTileBackground(branding: WidgetBranding): string {
  return `linear-gradient(135deg, ${branding.theme_color}, ${branding.secondary_color})`
}

/** Parse a hex color (#RGB, #RGBA, #RRGGBB, #RRGGBBAA) into [r, g, b] 0-255,
 * or null when unparseable. Alpha is ignored -- we only need the base hue for
 * the contrast decision below. */
function parseHexColor(color: string): [number, number, number] | null {
  if (typeof color !== 'string') return null
  const hex = color.trim().replace(/^#/, '')
  if (/^[0-9a-fA-F]{3}$/.test(hex) || /^[0-9a-fA-F]{4}$/.test(hex)) {
    return [
      parseInt(hex[0] + hex[0], 16),
      parseInt(hex[1] + hex[1], 16),
      parseInt(hex[2] + hex[2], 16),
    ]
  }
  if (/^[0-9a-fA-F]{6}$/.test(hex) || /^[0-9a-fA-F]{8}$/.test(hex)) {
    return [
      parseInt(hex.slice(0, 2), 16),
      parseInt(hex.slice(2, 4), 16),
      parseInt(hex.slice(4, 6), 16),
    ]
  }
  return null
}

/** WCAG relative luminance of an sRGB channel value (0-255). */
function channelLuminance(value: number): number {
  const c = value / 255
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

/**
 * Pick the more readable text color (white or near-black) for the given
 * background, using WCAG contrast ratios rather than a naive brightness
 * threshold. Handles #RGB/#RGBA/#RRGGBB/#RRGGBBAA; falls back to white when
 * the color can't be parsed (matches the widget's historical hardcoded
 * white-on-brand look).
 */
export function readableTextOn(bgColor: string): '#ffffff' | '#111827' {
  const rgb = parseHexColor(bgColor)
  if (!rgb) return '#ffffff'
  const bgLum =
    0.2126 * channelLuminance(rgb[0]) +
    0.7152 * channelLuminance(rgb[1]) +
    0.0722 * channelLuminance(rgb[2])
  // Contrast ratio = (lighter + 0.05) / (darker + 0.05). White has luminance
  // 1.0; #111827 (gray-900) has ~0.0084.
  const contrastWithWhite = (1.0 + 0.05) / (bgLum + 0.05)
  const contrastWithDark = (bgLum + 0.05) / (0.0084 + 0.05)
  return contrastWithWhite >= contrastWithDark ? '#ffffff' : '#111827'
}

/** WCAG contrast ratio between the given hex color and pure white. Returns
 * 21 (max contrast) when the color can't be parsed so callers never warn on
 * empty/auto values. Used by the live preview's low-contrast hint. */
export function contrastRatioWithWhite(color: string): number {
  const rgb = parseHexColor(color)
  if (!rgb) return 21
  const lum =
    0.2126 * channelLuminance(rgb[0]) +
    0.7152 * channelLuminance(rgb[1]) +
    0.0722 * channelLuminance(rgb[2])
  return (1.0 + 0.05) / (lum + 0.05)
}

export interface DerivedWidgetColors {
  bg: string
  text: string
  subtleBg: string
  headerBg: string
  headerText: string
  userBubbleBg: string
  assistantBubbleBg: string
  sendButtonBg: string
  borderColor: string
}

export function deriveWidgetColors(branding: WidgetBranding): DerivedWidgetColors {
  const isDark = branding.dark_mode
  const bg = branding.background_color || (isDark ? '#111827' : '#ffffff')
  const text = branding.text_color || (isDark ? '#f3f4f6' : '#111827')
  const subtleBg = isDark ? '#1f2937' : '#f3f4f6'
  return {
    bg,
    text,
    subtleBg,
    // Default header is clean/neutral (matches the Playground's chrome) --
    // the brand color lives in the avatar tile instead of a solid header
    // bar. Admins can still set header_bg_color for the classic colored-bar
    // look if they want it.
    headerBg: branding.header_bg_color || bg,
    headerText: branding.header_text_color || text,
    userBubbleBg: branding.user_bubble_color || branding.theme_color,
    assistantBubbleBg: branding.assistant_bubble_color || subtleBg,
    sendButtonBg: branding.send_button_color || branding.theme_color,
    borderColor: branding.border_color || (isDark ? '#374151' : '#e5e7eb'),
  }
}

export const LAUNCHER_ICON_SVG: Record<Exclude<WidgetLayout['launcher_icon'], 'custom'>, string> = {
  chat: '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  message: '<path d="M4 4h16v12H7l-3 3V4z" stroke="white" stroke-width="2" stroke-linejoin="round" fill="none"/>',
  robot: '<rect x="4" y="8" width="16" height="11" rx="2" stroke="white" stroke-width="2" fill="none"/><path d="M12 8V4M9 4h6" stroke="white" stroke-width="2" stroke-linecap="round"/><circle cx="9" cy="13.5" r="1.3" fill="white"/><circle cx="15" cy="13.5" r="1.3" fill="white"/>',
}
