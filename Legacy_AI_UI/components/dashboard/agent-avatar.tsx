'use client'

import type { AgentAvatarType } from '@/types'
import { ConnectorLogo } from '@/components/connectors/connector-logo'
import { getAgentSticker } from '@/lib/agent-stickers'
import { avatarColor, cn } from '@/lib/utils'

const SIZE_CLASSES = {
  xs: 'w-6 h-6 text-[10px]',
  sm: 'w-8 h-8 text-[11px]',
  md: 'w-12 h-12 text-lg',
  lg: 'w-12 h-12 text-xl',
} as const

const EMOJI_SIZE = {
  xs: 'text-sm',
  sm: 'text-base',
  md: 'text-2xl',
  lg: 'text-2xl',
} as const

export interface AgentAvatarProps {
  name: string
  avatarType?: AgentAvatarType | null
  avatarValue?: string | null
  avatarUrl?: string | null
  size?: keyof typeof SIZE_CLASSES
  shape?: 'circle' | 'rounded' | 'square'
  className?: string
}

export function resolveAgentAvatarColor(
  name: string,
  avatarType?: AgentAvatarType | null,
  avatarValue?: string | null,
): string {
  if (avatarType === 'color' && avatarValue) return avatarValue
  if (avatarType === 'sticker' && avatarValue) {
    return getAgentSticker(avatarValue)?.bg ?? avatarColor(name)
  }
  if (avatarType === 'emoji' && avatarValue) return avatarColor(name)
  return avatarColor(name)
}

export function AgentAvatar({
  name,
  avatarType = 'color',
  avatarValue,
  avatarUrl,
  size = 'sm',
  shape,
  className,
}: AgentAvatarProps) {
  const resolvedShape = shape ?? (avatarType === 'sticker' || avatarType === 'brand' ? 'square' : 'circle')
  const sizeClass = SIZE_CLASSES[size]
  const shapeClass =
    resolvedShape === 'circle' ? 'rounded-full' : resolvedShape === 'square' ? 'rounded-md' : 'rounded-lg'
  const initial = name ? name[0].toUpperCase() : '?'

  if (avatarType === 'image' && avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt=""
        className={cn(sizeClass, shapeClass, 'object-cover shrink-0', className)}
      />
    )
  }

  if (avatarType === 'brand' && avatarValue) {
    const logoSize = size === 'lg' || size === 'md' ? 'md' : 'sm'
    const scaleClass =
      size === 'xs' ? 'origin-center scale-[0.67]' : size === 'sm' ? 'origin-center scale-90' : undefined
    return (
      <ConnectorLogo
        providerId={avatarValue}
        size={logoSize}
        className={cn(scaleClass, className)}
      />
    )
  }

  if (avatarType === 'sticker' && avatarValue) {
    const sticker = getAgentSticker(avatarValue)
    if (sticker) {
      return (
        <div
          className={cn(
            sizeClass,
            shapeClass,
            sticker.bg,
            'flex items-center justify-center shrink-0 shadow-sm',
            className,
          )}
        >
          <span className={cn('leading-none select-none', EMOJI_SIZE[size])}>{sticker.emoji}</span>
        </div>
      )
    }
  }

  const colorClass = resolveAgentAvatarColor(name, avatarType, avatarValue)

  if (avatarType === 'emoji' && avatarValue) {
    return (
      <div
        className={cn(
          sizeClass,
          shapeClass,
          colorClass,
          'flex items-center justify-center font-semibold text-white shrink-0',
          className,
        )}
      >
        <span className={cn('leading-none', EMOJI_SIZE[size])}>{avatarValue}</span>
      </div>
    )
  }

  return (
    <div
      className={cn(
        sizeClass,
        shapeClass,
        colorClass,
        'flex items-center justify-center font-semibold text-white shrink-0',
        className,
      )}
    >
      {initial}
    </div>
  )
}
