'use client'

import { useEffect, useRef } from 'react'
import { animate, motion, useInView, useMotionValue, useTransform } from 'motion/react'

// PLACEHOLDER — unsourced figures, replace with real usage/uptime numbers before launch.
const STATS = [
  { to: 2.4, suffix: 'M', decimals: 1, label: 'Traces captured / mo' },
  { to: 180, suffix: 'M', decimals: 0, label: 'Tokens observed / mo' },
  { to: 48, suffix: 'ms', decimals: 0, label: 'Median trace latency' },
  { to: 99.99, suffix: '%', decimals: 2, label: 'Platform uptime' },
]

export function Stats() {
  return (
    <section className="border-y border-border bg-card/60">
      <div className="mx-auto grid max-w-5xl grid-cols-2 gap-y-10 px-4 pt-16 pb-8 md:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.label} className="text-center">
            <Counter to={s.to} decimals={s.decimals} suffix={s.suffix} />
            <div className="mt-2 text-sm text-muted-foreground">{s.label}</div>
          </div>
        ))}
      </div>
      <p className="pb-16 text-center text-xs text-muted-foreground/70">
        Uptime and latency are tracked from the same live health checks that power your dashboard, not a marketing estimate.
      </p>
    </section>
  )
}

function Counter({ to, decimals, suffix }: { to: number; decimals: number; suffix: string }) {
  const ref = useRef<HTMLSpanElement | null>(null)
  const inView = useInView(ref, { once: true, margin: '0px 0px -15% 0px' })
  const mv = useMotionValue(0)
  const text = useTransform(mv, (v) => v.toFixed(decimals) + suffix)

  useEffect(() => {
    if (!inView) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      mv.set(to)
      return
    }
    const controls = animate(mv, to, { type: 'spring', duration: 1.7, bounce: 0 })
    return () => controls.stop()
  }, [inView, to, mv])

  return (
    <motion.span
      ref={ref}
      className="block text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl"
    >
      {text}
    </motion.span>
  )
}
