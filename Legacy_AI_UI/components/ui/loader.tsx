'use client'

import { motion, useReducedMotion } from 'motion/react'
import { LogoMark } from '@/components/landing/logo'
import { cn } from '@/lib/utils'

interface LoaderProps {
  /** Overall diameter in pixels. */
  size?: number
  className?: string
  /** Optional caption shown under the mark. */
  label?: string
}

const RINGS = [
  { radius: 46, dash: '120 300', width: 3, duration: 2.4, direction: 1, color: 'text-violet-600 dark:text-violet-400', opacity: 1, comet: true },
  { radius: 37, dash: '70 300', width: 3, duration: 1.7, direction: -1, color: 'text-violet-400 dark:text-violet-500', opacity: 0.85, comet: false },
  { radius: 28, dash: '48 300', width: 2.5, duration: 1.15, direction: 1, color: 'text-violet-300 dark:text-violet-700', opacity: 0.6, comet: false },
] as const

/** Branded loading indicator — motion-driven counter-rotating arcs orbiting the ONE-AI mark. */
export function Loader({ size = 88, className, label }: LoaderProps) {
  const reduced = useReducedMotion()
  const markBox = Math.round(size * 0.4)
  const markIcon = Math.round(size * 0.21)

  return (
    <motion.div
      className={cn('inline-flex flex-col items-center gap-5', className)}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="relative" style={{ width: size, height: size }}>
        {/* Soft ambient glow behind the rings — flat blur, no gradient */}
        <motion.div
          className="absolute inset-0 rounded-full bg-violet-500/20 blur-xl"
          aria-hidden
          animate={reduced ? undefined : { opacity: [0.45, 0.85, 0.45], scale: [0.94, 1.04, 0.94] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
        />

        {RINGS.map((ring, i) => (
          <motion.svg
            key={i}
            viewBox="0 0 100 100"
            className="absolute inset-0"
            style={{ width: size, height: size, opacity: ring.opacity }}
            aria-hidden
            animate={reduced ? undefined : { rotate: 360 * ring.direction }}
            transition={{ duration: ring.duration, repeat: Infinity, ease: 'linear' }}
          >
            <circle
              cx="50"
              cy="50"
              r={ring.radius}
              fill="none"
              stroke="currentColor"
              strokeWidth={ring.width}
              strokeLinecap="round"
              strokeDasharray={ring.dash}
              className={ring.color}
            />
            {ring.comet && (
              <circle
                cx={50 + ring.radius}
                cy="50"
                r={ring.width * 0.9}
                className={cn(ring.color, 'drop-shadow-[0_0_6px_currentColor]')}
                fill="currentColor"
              />
            )}
          </motion.svg>
        ))}

        <div className="absolute inset-0 flex items-center justify-center">
          <motion.span
            className="inline-block"
            style={{ width: markBox, height: markBox }}
            animate={reduced ? undefined : { scale: [1, 1.07, 1] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
          >
            <motion.span
              className="flex items-center justify-center w-full h-full rounded-2xl bg-violet-600"
              animate={
                reduced
                  ? undefined
                  : {
                      boxShadow: [
                        '0 0 8px 2px rgba(124, 58, 237, 0.3)',
                        '0 0 16px 4px rgba(124, 58, 237, 0.5)',
                        '0 0 8px 2px rgba(124, 58, 237, 0.3)',
                      ],
                    }
              }
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            >
              <LogoMark className="text-white" size={markIcon} />
            </motion.span>
          </motion.span>
        </div>
      </div>
      {label && (
        <motion.p
          className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground"
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.3 }}
        >
          {label}
        </motion.p>
      )}
    </motion.div>
  )
}

/** Full-viewport variant — drop in for the root `app/loading.tsx` boundary or auth gates. */
export function FullscreenLoader({ label }: { label?: string }) {
  return (
    <div suppressHydrationWarning className="relative flex h-screen w-full items-center justify-center overflow-hidden bg-background">
      <div
        className="pointer-events-none absolute top-1/2 left-1/2 size-[28rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-500/10 blur-[120px]"
        aria-hidden
      />
      <Loader size={96} label={label} className="relative" />
    </div>
  )
}

/** In-content variant — centers within a route's content area (dashboard chrome stays put). */
export function PageLoader({ label, className }: { label?: string; className?: string }) {
  return (
    <div className={cn('relative flex min-h-[60vh] w-full items-center justify-center', className)}>
      <div
        className="pointer-events-none absolute top-1/2 left-1/2 size-[22rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-500/10 blur-[100px]"
        aria-hidden
      />
      <Loader size={80} label={label} className="relative" />
    </div>
  )
}
