'use client'

import { useEffect, useRef } from 'react'
import Link from 'next/link'
import { LucideIcon, TrendingUp, TrendingDown, ArrowUpRight } from 'lucide-react'
import { motion, animate, useMotionValue, useReducedMotion, useTransform } from 'motion/react'
import { cn } from '@/lib/utils'

interface StatsCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  trend?: number
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  /** When set, the whole card becomes a link into a drill-down view. */
  href?: string
}

const colorMap = {
  primary: {
    wrap:  'bg-violet-100 dark:bg-violet-900/30',
    icon:  'text-violet-600 dark:text-violet-400',
    glow:  'shadow-[0_0_16px_rgba(124,58,237,0.15)] dark:shadow-[0_0_16px_rgba(124,58,237,0.25)]',
  },
  success: {
    wrap:  'bg-green-100 dark:bg-green-900/30',
    icon:  'text-green-600 dark:text-green-400',
    glow:  'shadow-[0_0_16px_rgba(34,197,94,0.12)] dark:shadow-[0_0_16px_rgba(34,197,94,0.2)]',
  },
  warning: {
    wrap:  'bg-amber-100 dark:bg-amber-900/30',
    icon:  'text-amber-600 dark:text-amber-400',
    glow:  '',
  },
  danger: {
    wrap:  'bg-red-100 dark:bg-red-900/30',
    icon:  'text-red-600 dark:text-red-400',
    glow:  '',
  },
  info: {
    wrap:  'bg-cyan-100 dark:bg-cyan-900/30',
    icon:  'text-cyan-600 dark:text-cyan-400',
    glow:  '',
  },
}

/** Counts up/down from the previous value instead of snapping (AUDIT.md
 * category 8) — only used when `value` is a plain integer; anything else
 * (formatted strings, units, currency) renders as-is. */
function AnimatedValue({ value }: { value: number }) {
  const reducedMotion = useReducedMotion()
  const mv = useMotionValue(value)
  const display = useTransform(mv, v => Math.round(v).toLocaleString())
  const prevValue = useRef(value)

  useEffect(() => {
    if (prevValue.current === value) return
    prevValue.current = value
    if (reducedMotion) {
      mv.set(value)
      return
    }
    const controls = animate(mv, value, { duration: 0.5, ease: [0.16, 1, 0.3, 1] })
    return () => controls.stop()
  }, [value, mv, reducedMotion])

  return <motion.span>{display}</motion.span>
}

function isPlainInteger(value: string | number): value is number {
  if (typeof value === 'number') return Number.isFinite(value)
  return /^-?\d+$/.test(value.trim())
}

export function StatsCard({
  label,
  value,
  icon: Icon,
  trend = 0,
  color = 'primary',
  href,
}: StatsCardProps) {
  const c = colorMap[color]
  const content = (
    // Double-bezel: outer machined shell + inner display core (matches the
    // showcase product frame's nested-enclosure treatment).
    <div
      className={cn(
        'rounded-[1.5rem] border border-[var(--border)] bg-[var(--surface-2)]/60 p-1.5',
        'shadow-[inset_0_1px_0_0_oklch(1_0_0/0.08)]',
        'transition-shadow duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)]',
        href && 'group cursor-pointer',
      )}
    >
      <div className={cn('card-1 rounded-[calc(1.5rem-0.375rem)] p-4 flex flex-col gap-3', href ? 'group-hover:shadow-md' : 'hover:shadow-md')}>
        <div className="flex items-start justify-between">
          <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', c.wrap, c.glow)}>
            <Icon className={cn('w-5 h-5', c.icon)} />
          </div>
          {href && trend === 0 && (
            <ArrowUpRight className="w-4 h-4 text-[var(--text-3)] opacity-0 group-hover:opacity-100 transition-opacity duration-[120ms]" />
          )}
          {trend !== 0 && (
            <div className={cn(
              'flex items-center gap-1 text-[12px] font-semibold px-2 py-0.5 rounded-full',
              trend > 0
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
            )}>
              {trend > 0
                ? <TrendingUp className="w-3 h-3" />
                : <TrendingDown className="w-3 h-3" />
              }
              {trend > 0 ? '+' : ''}{trend}%
            </div>
          )}
        </div>
        <div>
          <p className="text-[var(--text-3)] text-[12px] font-medium">{label}</p>
          <p className="text-[26px] font-bold text-[var(--text-1)] mt-0.5 leading-none">
            {isPlainInteger(value) ? <AnimatedValue value={Number(value)} /> : value}
          </p>
        </div>
      </div>
    </div>
  )

  return href ? <Link href={href}>{content}</Link> : content
}
