'use client'

import { useEffect, useRef, useState } from 'react'
import { animate, AnimatePresence, motion, useMotionValue, useTransform, useInView } from 'motion/react'
import {
  Network,
  Headset,
  Wrench,
  Database,
  Sparkles,
  CheckCircle2,
  Coins,
  Timer,
  Hash,
} from 'lucide-react'
import { SectionHeading } from './section-heading'

type Step = {
  icon: React.ElementType
  label: string
  detail: string
  ms: number
  tokens: number
}

const STEPS: Step[] = [
  { icon: Network, label: 'Supervisor', detail: 'route → Support Agent', ms: 120, tokens: 0 },
  { icon: Headset, label: 'Support Agent', detail: 'plan response', ms: 340, tokens: 210 },
  { icon: Wrench, label: 'Tool call', detail: 'search_docs(query)', ms: 180, tokens: 0 },
  { icon: Database, label: 'Query', detail: 'Databricks · orders', ms: 95, tokens: 0 },
  { icon: Sparkles, label: 'Synthesize', detail: 'compose answer', ms: 420, tokens: 380 },
  { icon: CheckCircle2, label: 'Verify & respond', detail: 'guardrail check passed', ms: 110, tokens: 90 },
]

const COST_PER_1K = 0.003

export function TraceReplay() {
  const ref = useRef<HTMLDivElement | null>(null)
  const inView = useInView(ref, { once: false, margin: '0px 0px -20% 0px' })
  const [shown, setShown] = useState(0)
  const [reduce, setReduce] = useState(false)

  useEffect(() => {
    setReduce(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  }, [])

  useEffect(() => {
    if (reduce) {
      setShown(STEPS.length)
      return
    }
    if (!inView) return
    let t: ReturnType<typeof setTimeout>
    let i = 0
    setShown(0)
    const tick = () => {
      i += 1
      if (i <= STEPS.length) {
        setShown(i)
        t = setTimeout(tick, 680)
      } else {
        t = setTimeout(() => {
          i = 0
          setShown(0)
          t = setTimeout(tick, 680)
        }, 2800)
      }
    }
    t = setTimeout(tick, 450)
    return () => clearTimeout(t)
  }, [inView, reduce])

  const visible = STEPS.slice(0, shown)
  const tokens = visible.reduce((a, s) => a + s.tokens, 0)
  const latency = visible.reduce((a, s) => a + s.ms, 0)
  const cost = (tokens / 1000) * COST_PER_1K
  const done = shown >= STEPS.length

  return (
    <section className="relative mx-auto max-w-6xl px-4 py-24">
      <SectionHeading
        title="See every step as it happens"
        subtitle="Live traces capture each agent hop, tool call and token, with cost and latency rolled up in real time."
      />

      <div ref={ref} className="glass-card mx-auto mt-14 max-w-3xl overflow-hidden rounded-3xl border border-border bg-card/50 backdrop-blur-2xl backdrop-saturate-150">
        {/* window chrome */}
        <div className="flex items-center gap-2 border-b border-border px-5 py-3">
          <span className="size-3 rounded-full bg-muted-foreground/30" />
          <span className="size-3 rounded-full bg-muted-foreground/30" />
          <span className="size-3 rounded-full bg-muted-foreground/30" />
          <span className="ml-2 font-mono text-xs text-muted-foreground">trace · session_a1b2c3</span>
          <span
            className={`ml-auto inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
              done
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                : 'bg-violet-500/10 text-violet-600 dark:text-violet-300'
            }`}
          >
            <span className={`size-1.5 rounded-full ${done ? 'bg-emerald-500' : 'animate-pulse bg-violet-500'}`} />
            {done ? 'completed' : 'running'}
          </span>
        </div>

        {/* metric bar */}
        <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
          <Metric icon={Hash} label="Tokens" value={tokens} format={(v) => Math.round(v).toLocaleString()} />
          <Metric icon={Coins} label="Cost" value={cost} format={(v) => `$${v.toFixed(4)}`} />
          <Metric icon={Timer} label="Latency" value={latency} format={(v) => `${Math.round(v)}ms`} />
        </div>

        {/* steps */}
        <div className="space-y-2 p-5 min-h-[332px]">
          <AnimatePresence initial={false}>
            {visible.map((s, i) => (
              <motion.div
                key={`${s.label}-${i}`}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className="flex items-center gap-3 rounded-xl border border-border bg-background/50 px-4 py-2.5"
              >
                <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/12 text-violet-600 dark:text-violet-400">
                  <s.icon size={14} />
                </span>
                <span className="text-sm font-medium text-foreground">{s.label}</span>
                <span className="truncate font-mono text-xs text-muted-foreground">{s.detail}</span>
                <span className="ml-auto flex shrink-0 items-center gap-3 font-mono text-xs text-muted-foreground">
                  {s.tokens > 0 && <span>{s.tokens} tok</span>}
                  <span>{s.ms}ms</span>
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </section>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
  format,
}: {
  icon: React.ElementType
  label: string
  value: number
  format: (v: number) => string
}) {
  const mv = useMotionValue(0)
  const text = useTransform(mv, (v) => format(v))
  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.5, ease: 'easeOut' })
    return () => controls.stop()
  }, [value, mv])

  return (
    <div className="flex flex-col gap-1 px-5 py-4">
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon size={13} className="text-violet-500" />
        {label}
      </span>
      <motion.span className="font-mono text-xl font-bold text-foreground">{text}</motion.span>
    </div>
  )
}
