'use client'

import { motion, useScroll, useSpring } from 'motion/react'

/** Thin violet progress bar pinned to the very top, filling with scroll. */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 30, mass: 0.3 })

  return (
    <motion.div
      style={{ scaleX }}
      className="sentry-block fixed inset-x-0 top-0 z-[60] h-0.5 origin-left bg-violet-600 dark:bg-violet-400"
      aria-hidden
    />
  )
}
