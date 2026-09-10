'use client'

import { useRef } from 'react'
import {
  motion,
  useAnimationFrame,
  useInView,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  useVelocity,
  wrap,
} from 'motion/react'

/**
 * Marquee whose speed and skew react to scroll velocity (Framer Motion).
 * Scrolling fast speeds it up and skews it slightly; direction follows scroll.
 * Renders children twice for a seamless loop.
 */
export function VelocityMarquee({
  children,
  baseVelocity = 4,
  className,
}: {
  children: React.ReactNode
  baseVelocity?: number
  className?: string
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const inView = useInView(viewportRef, { margin: '200px 0px 200px 0px' })

  const baseX = useMotionValue(0)
  const { scrollY } = useScroll()
  const scrollVelocity = useVelocity(scrollY)
  const smoothVelocity = useSpring(scrollVelocity, { damping: 50, stiffness: 400 })
  const velocityFactor = useTransform(smoothVelocity, [0, 1000], [0, 5], { clamp: false })
  const skew = useTransform(smoothVelocity, [-1000, 0, 1000], [-4, 0, 4], { clamp: true })

  const x = useTransform(baseX, (v) => `${wrap(-50, 0, v)}%`)

  // A permanent per-frame animation loop is exactly the kind of continuous,
  // velocity-reactive motion prefers-reduced-motion exists for (AUDIT.md
  // category 6) — skip the loop entirely rather than just softening it.
  const reducedMotion = useReducedMotion()
  // Pause on hover/focus so the (often prose) content is actually readable
  // (AUDIT.md category 8 — continuous content needs a way to stop and consume it).
  const paused = useRef(false)
  const directionFactor = useRef(1)
  useAnimationFrame((_t, delta) => {
    if (reducedMotion || paused.current || !inView) return
    let moveBy = directionFactor.current * baseVelocity * (delta / 1000)
    if (velocityFactor.get() < 0) directionFactor.current = -1
    else if (velocityFactor.get() > 0) directionFactor.current = 1
    moveBy += directionFactor.current * moveBy * velocityFactor.get()
    baseX.set(baseX.get() + moveBy)
  })

  if (reducedMotion) {
    return (
      <div ref={viewportRef} className={`relative overflow-x-auto ${className ?? ''}`}>
        <div className="flex w-max flex-nowrap">{children}</div>
      </div>
    )
  }

  return (
    <div
      ref={viewportRef}
      className={`relative overflow-hidden ${className ?? ''}`}
      onPointerEnter={() => { paused.current = true }}
      onPointerLeave={() => { paused.current = false }}
      onFocus={() => { paused.current = true }}
      onBlur={() => { paused.current = false }}
    >
      <motion.div style={{ x, skewX: skew }} className="flex w-max flex-nowrap">
        <div className="flex shrink-0 items-center">{children}</div>
        <div className="flex shrink-0 items-center" aria-hidden>
          {children}
        </div>
      </motion.div>
    </div>
  )
}
