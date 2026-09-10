'use client'

import { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'motion/react'
import { Boxes, Database, Network, Cog, BarChart3, Headset, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import { SectionHeading } from './section-heading'

const S = { x: 50, y: 15 }
const A = [
  { x: 18, y: 50 },
  { x: 50, y: 50 },
  { x: 82, y: 50 },
]
const R = [
  { x: 18, y: 86 },
  { x: 50, y: 86 },
  { x: 82, y: 86 },
]

const AGENTS = [
  { name: 'Support Agent', icon: Headset },
  { name: 'Data Analyst', icon: BarChart3 },
  { name: 'Ops Agent', icon: Cog },
]
const RESOURCES = [
  { name: 'search_docs', icon: Wrench },
  { name: 'Databricks', icon: Database },
  { name: 'Tool Registry', icon: Boxes },
]

export function Orchestration() {
  const ref = useRef<HTMLDivElement | null>(null)
  const inView = useInView(ref, { once: false, margin: '0px 0px -20% 0px' })
  const [active, setActive] = useState(1)
  const [reduce, setReduce] = useState(false)
  // The dot's path is defined in percent-of-container coordinates, but animating
  // `left`/`top` triggers layout every frame (AUDIT.md category 5). Track the
  // container's actual pixel size so the travelling dot can animate a single
  // `transform: translate()` string instead.
  const [size, setSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    setReduce(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  }, [])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ width, height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!inView || reduce) return
    const id = setInterval(() => setActive((i) => (i + 1) % AGENTS.length), 2400)
    return () => clearInterval(id)
  }, [inView, reduce])

  const pulse = !reduce && inView

  return (
    <section className="relative mx-auto max-w-6xl px-4 py-24">
      <SectionHeading
        eyebrow="Multi-agent orchestration"
        title="One supervisor, a fleet of specialists"
        subtitle="A supervisor routes each request to the right agent, which calls the tools and data it needs, then reports back. Every hop is governed and traced."
      />

      <div
        ref={ref}
        className="relative mx-auto mt-14 h-[440px] w-full max-w-3xl sm:h-[500px]"
      >
        {/* connectors */}
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden
        >
          {A.map((a, i) => (
            <line
              key={`base-sa-${i}`}
              x1={S.x} y1={S.y} x2={a.x} y2={a.y}
              stroke="var(--border)" strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {A.map((a, i) => (
            <line
              key={`base-ar-${i}`}
              x1={a.x} y1={a.y} x2={R[i].x} y2={R[i].y}
              stroke="var(--border)" strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {/* active path */}
          <line
            x1={S.x} y1={S.y} x2={A[active].x} y2={A[active].y}
            className={cn('text-violet-500', pulse && 'edge-flow')}
            stroke="currentColor" strokeWidth={2} vectorEffect="non-scaling-stroke"
          />
          <line
            x1={A[active].x} y1={A[active].y} x2={R[active].x} y2={R[active].y}
            className={cn('text-violet-500', pulse && 'edge-flow')}
            stroke="currentColor" strokeWidth={2} vectorEffect="non-scaling-stroke"
          />
        </svg>

        {/* travelling pulse — animates a single `transform` (computed from the
            measured container size), not left/top, so it composites on the GPU
            instead of triggering layout every frame (AUDIT.md category 5). */}
        {pulse && size.width > 0 && (() => {
          const toPx = (pt: { x: number; y: number }) => ({
            x: (pt.x / 100) * size.width,
            y: (pt.y / 100) * size.height,
          })
          const sPx = toPx(S)
          const aPx = toPx(A[active])
          const rPx = toPx(R[active])
          return (
            <motion.span
              key={active}
              initial={{ transform: `translate(${sPx.x}px, ${sPx.y}px) translate(-50%, -50%)` }}
              animate={{
                transform: [
                  `translate(${sPx.x}px, ${sPx.y}px) translate(-50%, -50%)`,
                  `translate(${aPx.x}px, ${aPx.y}px) translate(-50%, -50%)`,
                  `translate(${rPx.x}px, ${rPx.y}px) translate(-50%, -50%)`,
                ],
              }}
              transition={{ duration: 1.8, times: [0, 0.5, 1], ease: [0.77, 0, 0.175, 1] }}
              className="absolute left-0 top-0 z-20 size-2.5 rounded-full bg-violet-500 shadow-[0_0_12px_3px_rgba(124,58,237,0.6)]"
            />
          )
        })()}

        {/* supervisor */}
        <Node x={S.x} y={S.y} active highlight>
          <Network size={16} className="text-violet-600 dark:text-violet-400" />
          Supervisor
        </Node>

        {/* agents */}
        {AGENTS.map((ag, i) => (
          <Node key={ag.name} x={A[i].x} y={A[i].y} active={i === active} onMouseEnter={() => setActive(i)}>
            <ag.icon
              size={15}
              className={i === active ? 'text-violet-600 dark:text-violet-400' : 'text-muted-foreground'}
            />
            {ag.name}
          </Node>
        ))}

        {/* resources */}
        {RESOURCES.map((rs, i) => (
          <Node key={rs.name} x={R[i].x} y={R[i].y} active={i === active} muted onMouseEnter={() => setActive(i)}>
            <rs.icon
              size={14}
              className={i === active ? 'text-violet-600 dark:text-violet-400' : 'text-muted-foreground'}
            />
            {rs.name}
          </Node>
        ))}
      </div>
    </section>
  )
}

function Node({
  x,
  y,
  active,
  highlight,
  muted,
  children,
  onMouseEnter,
}: {
  x: number
  y: number
  active?: boolean
  highlight?: boolean
  muted?: boolean
  children: React.ReactNode
  onMouseEnter?: () => void
}) {
  return (
    <div
      style={{ left: `${x}%`, top: `${y}%` }}
      onMouseEnter={onMouseEnter}
      className={cn(
        'glass-card absolute z-10 flex -translate-x-1/2 -translate-y-1/2 items-center gap-1 whitespace-nowrap rounded-xl border bg-card/70 px-2 py-1.5 text-[10px] font-semibold backdrop-blur-2xl backdrop-saturate-150 transition-[border-color,box-shadow,color] duration-300 sm:gap-1.5 sm:px-3 sm:py-2 sm:text-xs',
        muted ? 'font-mono text-[9px] sm:text-[11px]' : '',
        active
          ? 'border-violet-500/55 text-foreground shadow-[0_0_0_1px_rgba(124,58,237,0.25),0_14px_36px_-18px_rgba(124,58,237,0.65)]'
          : 'border-border text-foreground/70',
        highlight && 'px-2.5 py-2 text-xs sm:px-4 sm:py-2.5 sm:text-sm',
      )}
    >
      {children}
    </div>
  )
}
