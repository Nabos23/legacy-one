'use client'

import { useEffect, useRef, useState } from 'react'
import { Camera, Check, ChevronDown, ChevronUp, Loader2, Trash2, Upload } from 'lucide-react'
import type { AgentAvatarType } from '@/types'
import {
  AGENT_BRAND_CATEGORIES,
  ALL_BRAND_ICONS,
  BRAND_ICON_COUNT,
  DEFAULT_BRAND_ICON_ID,
  getBrandIcon,
  isBrandIconId,
} from '@/lib/agent-brand-icons'
import {
  AGENT_STICKER_CATEGORIES,
  ALL_AGENT_STICKERS,
  DEFAULT_AGENT_STICKER_ID,
  getAgentSticker,
  isAgentStickerId,
  STICKER_COUNT,
} from '@/lib/agent-stickers'
import { AVATAR_COLORS, cn } from '@/lib/utils'
import { ConnectorLogo } from '@/components/connectors/connector-logo'
import { AgentAvatar } from './agent-avatar'

const MAX_AVATAR_BYTES = 5 * 1024 * 1024
const ACCEPTED_AVATAR_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']

const TABS: { id: AgentAvatarType; label: string }[] = [
  { id: 'brand', label: 'Platforms' },
  { id: 'sticker', label: 'Icons' },
  { id: 'color', label: 'Color' },
  { id: 'image', label: 'Upload' },
]

export interface AgentAvatarSelection {
  avatarType: AgentAvatarType
  avatarValue: string
  avatarUrl?: string | null
  avatarPreviewUrl?: string | null
  avatarFile?: File | null
}

/** Resolve the URL to display for image avatars (local blob or server URL). */
export function resolveAvatarImageUrl(
  selection: Pick<AgentAvatarSelection, 'avatarType' | 'avatarUrl' | 'avatarPreviewUrl'>,
): string | null {
  if (selection.avatarType !== 'image') return null
  return selection.avatarPreviewUrl ?? selection.avatarUrl ?? null
}

export function getAvatarDisplayProps(
  selection: AgentAvatarSelection,
): Pick<AgentAvatarSelection, 'avatarType' | 'avatarValue' | 'avatarUrl'> & {
  shape?: 'circle' | 'rounded' | 'square'
} {
  const imageUrl = resolveAvatarImageUrl(selection)
  if (selection.avatarType === 'image' && imageUrl) {
    return {
      avatarType: 'image',
      avatarValue: '',
      avatarUrl: imageUrl,
      shape: 'rounded',
    }
  }
  if (selection.avatarType === 'sticker') {
    return {
      avatarType: 'sticker',
      avatarValue: selection.avatarValue,
      avatarUrl: null,
      shape: 'square',
    }
  }
  if (selection.avatarType === 'brand') {
    return {
      avatarType: 'brand',
      avatarValue: selection.avatarValue,
      avatarUrl: null,
      shape: 'square',
    }
  }
  return {
    avatarType: selection.avatarType,
    avatarValue: selection.avatarValue,
    avatarUrl: selection.avatarUrl ?? null,
    shape: 'circle',
  }
}

interface AgentAvatarPickerProps {
  name: string
  value: AgentAvatarSelection
  onChange: (value: AgentAvatarSelection) => void
  onUpload?: (file: File) => Promise<string | null>
  uploading?: boolean
}

export function AgentAvatarPicker({
  name,
  value,
  onChange,
  onUpload,
  uploading = false,
}: AgentAvatarPickerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [galleryExpanded, setGalleryExpanded] = useState(false)

  const previewUrl = resolveAvatarImageUrl(value)
  const hasSelectedImage = value.avatarType === 'image' && !!previewUrl
  const displayProps = getAvatarDisplayProps(value)

  const revokePreviewUrl = (url: string | null | undefined) => {
    if (url?.startsWith('blob:')) URL.revokeObjectURL(url)
  }

  const applyImageSelection = (next: Partial<AgentAvatarSelection>) => {
    onChange({
      ...value,
      avatarType: 'image',
      avatarValue: '',
      avatarFile: null,
      ...next,
    })
  }

  const clearImageSelection = () => {
    revokePreviewUrl(value.avatarPreviewUrl)
    onChange({
      avatarType: 'sticker',
      avatarValue: DEFAULT_AGENT_STICKER_ID,
      avatarUrl: null,
      avatarPreviewUrl: null,
      avatarFile: null,
    })
  }

  useEffect(() => () => revokePreviewUrl(value.avatarPreviewUrl), [value.avatarPreviewUrl])

  const selectTab = (tab: AgentAvatarType) => {
    setGalleryExpanded(false)
    if (tab === value.avatarType) return
    if (tab === 'brand') {
      onChange({
        avatarType: 'brand',
        avatarValue:
          value.avatarType === 'brand' && isBrandIconId(value.avatarValue)
            ? value.avatarValue
            : DEFAULT_BRAND_ICON_ID,
        avatarUrl: value.avatarUrl,
        avatarPreviewUrl: value.avatarPreviewUrl,
        avatarFile: null,
      })
      return
    }
    if (tab === 'sticker') {
      onChange({
        avatarType: 'sticker',
        avatarValue:
          value.avatarType === 'sticker' && isAgentStickerId(value.avatarValue)
            ? value.avatarValue
            : DEFAULT_AGENT_STICKER_ID,
        avatarUrl: value.avatarUrl,
        avatarPreviewUrl: value.avatarPreviewUrl,
        avatarFile: null,
      })
      return
    }
    if (tab === 'color') {
      onChange({
        avatarType: 'color',
        avatarValue:
          value.avatarValue && AVATAR_COLORS.includes(value.avatarValue as (typeof AVATAR_COLORS)[number])
            ? value.avatarValue
            : AVATAR_COLORS[0],
        avatarUrl: value.avatarUrl,
        avatarPreviewUrl: value.avatarPreviewUrl,
        avatarFile: null,
      })
      return
    }
    onChange({
      avatarType: 'image',
      avatarValue: '',
      avatarUrl: value.avatarUrl,
      avatarPreviewUrl: value.avatarPreviewUrl,
      avatarFile: value.avatarFile ?? null,
    })
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return

    setUploadError(null)
    if (!ACCEPTED_AVATAR_TYPES.includes(file.type)) {
      setUploadError('Upload a PNG, JPEG, GIF, or WEBP image')
      return
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setUploadError('Image must be under 5MB')
      return
    }

    if (onUpload) {
      try {
        const uploadedUrl = await onUpload(file)
        revokePreviewUrl(value.avatarPreviewUrl)
        applyImageSelection({
          avatarUrl: uploadedUrl,
          avatarPreviewUrl: uploadedUrl,
          avatarFile: null,
        })
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : 'Could not upload image')
      }
      return
    }

    revokePreviewUrl(value.avatarPreviewUrl)
    const blobUrl = URL.createObjectURL(file)
    applyImageSelection({
      avatarUrl: value.avatarUrl,
      avatarPreviewUrl: blobUrl,
      avatarFile: file,
    })
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="text-[13px] font-medium block mb-2">
          Choose a profile icon
          <span className="ml-2 text-[11px] font-normal text-[var(--text-3)]">
            {value.avatarType === 'brand'
              ? `${BRAND_ICON_COUNT} platforms`
              : value.avatarType === 'sticker'
                ? `${STICKER_COUNT} icons`
                : ''}
          </span>
        </label>
        <div className="inline-flex rounded-lg border border-[var(--border)] p-1 gap-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => selectTab(tab.id)}
              className={cn(
                'px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors',
                value.avatarType === tab.id
                  ? 'bg-violet-600 text-white'
                  : 'text-[var(--text-3)] hover:text-[var(--text-1)]',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {value.avatarType === 'brand' && (
        !galleryExpanded ? (
          <div className="relative rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)]/40 p-2.5">
            <div className="flex items-center gap-2 overflow-x-auto py-1.5 pr-8 custom-scrollbar">
              {ALL_BRAND_ICONS.map(brand => {
                const selected = value.avatarValue === brand.id
                return (
                  <button
                    key={brand.id}
                    type="button"
                    title={brand.label}
                    onClick={() =>
                      onChange({ ...value, avatarType: 'brand', avatarValue: brand.id, avatarFile: null })
                    }
                    className={cn(
                      'transition-[transform,box-shadow] shrink-0 rounded-xl',
                      selected
                        ? 'ring-2 ring-violet-500 ring-offset-2 ring-offset-[var(--surface)] scale-105 shadow-md'
                        : 'hover:scale-105 hover:shadow-md opacity-90 hover:opacity-100',
                    )}
                  >
                    <ConnectorLogo providerId={brand.id} size="md" />
                  </button>
                )
              })}
            </div>
            <div className="pointer-events-none absolute right-0 top-0 bottom-1 w-10 bg-gradient-to-l from-[var(--surface)] to-transparent rounded-r-[var(--radius-lg)]" />
            <button
              type="button"
              onClick={() => setGalleryExpanded(true)}
              className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-violet-600 dark:text-violet-400 hover:text-violet-500 transition-colors"
            >
              Show all {BRAND_ICON_COUNT} platforms
              <ChevronDown className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="space-y-4 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
            <div className="max-h-[400px] overflow-y-auto pr-1 custom-scrollbar space-y-4">
              {AGENT_BRAND_CATEGORIES.map(category => (
                <div key={category.title}>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-3)] mb-2">
                    {category.title}
                  </p>
                  <div className="flex gap-2 flex-wrap">
                    {category.brands.map(brand => {
                      const selected = value.avatarValue === brand.id
                      return (
                        <button
                          key={brand.id}
                          type="button"
                          title={brand.label}
                          onClick={() =>
                            onChange({ ...value, avatarType: 'brand', avatarValue: brand.id, avatarFile: null })
                          }
                          className={cn(
                            'transition-[transform,box-shadow] shrink-0 rounded-xl',
                            selected
                              ? 'ring-2 ring-violet-500 ring-offset-2 ring-offset-[var(--surface)] scale-105 shadow-md'
                              : 'hover:scale-105 hover:shadow-md opacity-90 hover:opacity-100',
                          )}
                        >
                          <ConnectorLogo providerId={brand.id} size="md" />
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setGalleryExpanded(false)}
              className="inline-flex items-center gap-1 text-[12px] font-medium text-violet-600 dark:text-violet-400 hover:text-violet-500 transition-colors"
            >
              Show less
              <ChevronUp className="w-3.5 h-3.5" />
            </button>
          </div>
        )
      )}

      {value.avatarType === 'sticker' && (
        !galleryExpanded ? (
          <div className="relative rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)]/40 p-2.5">
            <div className="flex items-center gap-2 overflow-x-auto py-1.5 pr-8 custom-scrollbar">
              {ALL_AGENT_STICKERS.map(sticker => {
                const selected = value.avatarValue === sticker.id
                return (
                  <button
                    key={sticker.id}
                    type="button"
                    title={sticker.id}
                    onClick={() =>
                      onChange({ ...value, avatarType: 'sticker', avatarValue: sticker.id, avatarFile: null })
                    }
                    className={cn(
                      'w-12 h-12 rounded-md flex items-center justify-center text-2xl transition-[transform,box-shadow] shrink-0',
                      sticker.bg,
                      selected
                        ? 'ring-2 ring-white ring-offset-2 ring-offset-[var(--surface)] scale-105 shadow-md'
                        : 'hover:scale-105 hover:shadow-md opacity-90 hover:opacity-100',
                    )}
                  >
                    {sticker.emoji}
                  </button>
                )
              })}
            </div>
            <div className="pointer-events-none absolute right-0 top-0 bottom-1 w-10 bg-gradient-to-l from-[var(--surface)] to-transparent rounded-r-[var(--radius-lg)]" />
            <button
              type="button"
              onClick={() => setGalleryExpanded(true)}
              className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-violet-600 dark:text-violet-400 hover:text-violet-500 transition-colors"
            >
              Show all {STICKER_COUNT} icons
              <ChevronDown className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="space-y-4 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)]/40 p-3">
            <div className="max-h-[400px] overflow-y-auto pr-1 custom-scrollbar space-y-4">
              {AGENT_STICKER_CATEGORIES.map(category => (
                <div key={category.title}>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-3)] mb-2">
                    {category.title}
                  </p>
                  <div className="flex gap-2 flex-wrap">
                    {category.stickers.map(sticker => {
                      const selected = value.avatarValue === sticker.id
                      return (
                        <button
                          key={sticker.id}
                          type="button"
                          title={sticker.id}
                          onClick={() =>
                            onChange({ ...value, avatarType: 'sticker', avatarValue: sticker.id, avatarFile: null })
                          }
                          className={cn(
                            'w-12 h-12 rounded-md flex items-center justify-center text-2xl transition-[transform,box-shadow] shrink-0',
                            sticker.bg,
                            selected
                              ? 'ring-2 ring-white ring-offset-2 ring-offset-[var(--surface)] scale-105 shadow-md'
                              : 'hover:scale-105 hover:shadow-md opacity-90 hover:opacity-100',
                          )}
                        >
                          {sticker.emoji}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setGalleryExpanded(false)}
              className="inline-flex items-center gap-1 text-[12px] font-medium text-violet-600 dark:text-violet-400 hover:text-violet-500 transition-colors"
            >
              Show less
              <ChevronUp className="w-3.5 h-3.5" />
            </button>
          </div>
        )
      )}

      {value.avatarType === 'color' && (
        <div className="grid grid-cols-8 sm:grid-cols-12 gap-2 max-h-[200px] overflow-y-auto rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)]/40 p-3 custom-scrollbar">
          {AVATAR_COLORS.map(color => (
            <button
              key={color}
              type="button"
              onClick={() => onChange({ ...value, avatarType: 'color', avatarValue: color, avatarFile: null })}
              className={cn(
                'w-8 h-8 rounded-md transition-transform',
                color,
                value.avatarValue === color && 'ring-2 ring-white ring-offset-1 ring-offset-[var(--surface)] scale-110',
              )}
            />
          ))}
        </div>
      )}

      {value.avatarType === 'image' && (
        <div className="space-y-3">
          <div
            className={cn(
              'rounded-[var(--radius-lg)] border-2 transition-colors',
              hasSelectedImage
                ? 'border-violet-500/60 bg-violet-500/5'
                : 'border-dashed border-[var(--border-2)]',
            )}
          >
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="flex items-center justify-center gap-2 w-full min-h-[140px] transition-colors hover:bg-black/[0.02] dark:hover:bg-white/[0.02] disabled:opacity-60 rounded-[var(--radius-lg)]"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-[13px] text-[var(--text-3)]">Uploading…</span>
                </>
              ) : hasSelectedImage ? (
                <div className="flex flex-col items-center gap-3 py-5 px-4">
                  <div className="relative">
                    <img
                      src={previewUrl!}
                      alt=""
                      className="w-24 h-24 rounded-xl object-cover ring-2 ring-violet-500/30 shadow-md"
                    />
                    <span className="absolute -top-2 -right-2 flex items-center justify-center w-6 h-6 rounded-full bg-violet-600 text-white shadow">
                      <Check className="w-3.5 h-3.5" />
                    </span>
                  </div>
                  <div className="text-center">
                    <p className="text-[13px] font-medium text-[var(--text-1)]">Image selected</p>
                    <p className="text-[12px] text-[var(--text-3)] mt-0.5">Click to choose a different image</p>
                  </div>
                </div>
              ) : (
                <>
                  <Upload className="w-4 h-4 text-[var(--text-3)]" />
                  <span className="text-[13px] text-[var(--text-3)]">Choose an image from your device</span>
                </>
              )}
            </button>
          </div>

          {hasSelectedImage && (
            <button
              type="button"
              onClick={clearImageSelection}
              className="inline-flex items-center gap-1.5 text-[12px] text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Remove image
            </button>
          )}

          <p className="text-[11px] text-[var(--text-3)]">PNG, JPEG, GIF, or WEBP · max 5MB</p>
          {uploadError && <p className="text-[12px] text-red-500 dark:text-red-400">{uploadError}</p>}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_AVATAR_TYPES.join(',')}
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
      )}

      <div className="flex items-center gap-3 pt-1">
        <div className="relative shrink-0">
          <AgentAvatar
            name={name}
            avatarType={displayProps.avatarType}
            avatarValue={displayProps.avatarValue}
            avatarUrl={displayProps.avatarUrl}
            size="md"
            shape={displayProps.shape}
          />
          {value.avatarType === 'image' && !hasSelectedImage && (
            <div className="absolute -bottom-1 -right-1 flex items-center justify-center w-7 h-7 rounded-full bg-violet-600 text-white shadow-md">
              <Camera className="w-3.5 h-3.5" />
            </div>
          )}
        </div>
        <p className="text-[12px] text-[var(--text-3)]">
          {value.avatarType === 'image' && hasSelectedImage
            ? 'Custom image selected — it will be used as this agent\'s avatar.'
            : value.avatarType === 'brand' && getBrandIcon(value.avatarValue)
              ? `Selected: ${getBrandIcon(value.avatarValue)!.label} platform logo`
              : value.avatarType === 'sticker' && getAgentSticker(value.avatarValue)
                ? `Selected: ${getAgentSticker(value.avatarValue)!.emoji} · ${AGENT_STICKER_CATEGORIES.find(c => c.stickers.some(s => s.id === value.avatarValue))?.title ?? 'Icon'}`
                : 'Preview updates as you customize the avatar.'}
        </p>
      </div>
    </div>
  )
}

export function buildAvatarApiPayload(selection: AgentAvatarSelection) {
  if (selection.avatarType === 'image') {
    return {}
  }
  return {
    avatar_type: selection.avatarType,
    avatar_value: selection.avatarValue || null,
  }
}

/** Normalize legacy draft/API values into the current selection shape. */
export function normalizeAvatarSelection(
  partial: Partial<AgentAvatarSelection> & { avatarColor?: string },
): AgentAvatarSelection {
  if (partial.avatarType === 'brand' && isBrandIconId(partial.avatarValue)) {
    return {
      avatarType: 'brand',
      avatarValue: partial.avatarValue!,
      avatarUrl: partial.avatarUrl ?? null,
    }
  }
  if (partial.avatarType === 'sticker' && isAgentStickerId(partial.avatarValue)) {
    return {
      avatarType: 'sticker',
      avatarValue: partial.avatarValue!,
      avatarUrl: partial.avatarUrl ?? null,
    }
  }
  if (partial.avatarType === 'emoji' && partial.avatarValue) {
    return {
      avatarType: 'emoji',
      avatarValue: partial.avatarValue,
      avatarUrl: partial.avatarUrl ?? null,
    }
  }
  if (partial.avatarType === 'image') {
    return {
      avatarType: 'image',
      avatarValue: '',
      avatarUrl: partial.avatarUrl ?? null,
      avatarPreviewUrl: partial.avatarPreviewUrl ?? partial.avatarUrl ?? null,
    }
  }
  const colorValue =
    partial.avatarValue && AVATAR_COLORS.includes(partial.avatarValue as (typeof AVATAR_COLORS)[number])
      ? partial.avatarValue
      : partial.avatarColor && AVATAR_COLORS.includes(partial.avatarColor as (typeof AVATAR_COLORS)[number])
        ? partial.avatarColor
        : AVATAR_COLORS[0]
  if (partial.avatarType === 'color' || partial.avatarColor) {
    return {
      avatarType: 'color',
      avatarValue: colorValue,
      avatarUrl: partial.avatarUrl ?? null,
    }
  }
  return {
    avatarType: 'sticker',
    avatarValue: DEFAULT_AGENT_STICKER_ID,
    avatarUrl: partial.avatarUrl ?? null,
  }
}
