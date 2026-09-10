'use client'

import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Bot, Activity, Wrench, CheckCircle2, TerminalSquare, GitBranch, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useGsapScroll } from '@/hooks/use-gsap-scroll'

type Shot = {
  key: string
  label: string
  icon: React.ElementType
  /** Drop a real screenshot at public/showcase/<src> to replace the mock. */
  src: string
  alt: string
  width: number
  height: number
}

const SHOTS: Shot[] = [
  { key: 'agents', label: 'Agents', icon: Bot, src: '/showcase/agents.png', alt: 'ONE-AI agents dashboard', width: 1612, height: 880 },
  { key: 'orchestrations', label: 'Orchestrations', icon: GitBranch, src: '/showcase/orchestrations.png', alt: 'ONE-AI multi-agent orchestration canvas', width: 1606, height: 835 },
  { key: 'tracing', label: 'Tracing', icon: Activity, src: '/showcase/tracing.png', alt: 'ONE-AI live tracing view', width: 1627, height: 880 },
  { key: 'playground', label: 'Playground', icon: TerminalSquare, src: '/showcase/playground.png', alt: 'ONE-AI playground', width: 1665, height: 922 },
]

export function Showcase() {
  const [active, setActive] = useState(SHOTS[0].key)
  const scope = useGsapScroll<HTMLDivElement>((gsap, _ST, el) => {
    const frame = el.querySelector('[data-frame]')
    if (frame) {
      gsap.fromTo(
        frame,
        { rotateX: 12, y: 60 },
        {
          rotateX: 0,
          y: 0,
          ease: 'none',
          scrollTrigger: { trigger: el, start: 'top 85%', end: 'top 35%', scrub: true },
        },
      )
    }
    const blob = el.querySelector('[data-blob]')
    if (blob) {
      gsap.to(blob, {
        yPercent: -35,
        ease: 'none',
        scrollTrigger: { trigger: el, start: 'top bottom', end: 'bottom top', scrub: true },
      })
    }
    // Depth-layered drift for the floating stat chips flanking the product
    // frame — each moves at its own speed while the section scrolls through
    // the viewport, so the frame reads as sitting in front of/behind them.
    gsap.utils.toArray<HTMLElement>(el.querySelectorAll('[data-parallax]')).forEach((node) => {
      const depth = Number(node.dataset.parallax) || 0.3
      gsap.to(node, {
        yPercent: -40 * depth,
        ease: 'none',
        scrollTrigger: { trigger: el, start: 'top bottom', end: 'bottom top', scrub: true },
      })
    })
  })

  const current = SHOTS.find((s) => s.key === active) ?? SHOTS[0]

  return (
    <section
      id="showcase"
      ref={scope}
      className="relative mx-auto max-w-6xl scroll-mt-24 px-4 py-24"
      style={{ perspective: '1200px' }}
    >
      <div
        data-blob
        className="sentry-block gpu-layer pointer-events-none absolute left-1/2 top-1/3 size-[30rem] -translate-x-1/2 rounded-full bg-violet-500/10 blur-[130px]"
      />
      {/* floating stat chips — different scroll speeds give the frame depth */}
      <div
        data-parallax="0.7"
        className="glass-card pointer-events-none absolute left-[2%] top-[22%] z-10 hidden animate-floatY items-center gap-3 rounded-2xl border border-border bg-card/60 px-4 py-3 backdrop-blur-2xl backdrop-saturate-150 lg:flex"
      >
        <span className="flex size-9 items-center justify-center rounded-xl bg-violet-500/12">
          <Zap size={16} className="text-violet-500" />
        </span>
        <span className="flex flex-col text-left">
          <span className="text-lg font-bold leading-none text-foreground">312ms</span>
          <span className="text-xs text-muted-foreground">Avg trace latency</span>
        </span>
      </div>
      <div
        data-parallax="0.35"
        className="glass-card pointer-events-none absolute right-[3%] bottom-[16%] z-10 hidden animate-floatY items-center gap-3 rounded-2xl border border-border bg-card/60 px-4 py-3 backdrop-blur-2xl backdrop-saturate-150 lg:flex"
      >
        <span className="flex size-9 items-center justify-center rounded-xl bg-violet-500/12">
          <CheckCircle2 size={16} className="text-emerald-500" />
        </span>
        <span className="flex flex-col text-left">
          <span className="text-lg font-bold leading-none text-foreground">4 agents</span>
          <span className="text-xs text-muted-foreground">Active on this run</span>
        </span>
      </div>

      <div className="mx-auto mb-10 max-w-2xl text-center">
        <h2 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
          A workspace built for agent teams
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
          Everything from prototyping to production observability in a single,
          glass-clear interface.
        </p>
      </div>

      {/* tabs */}
      <div className="mb-6 flex flex-wrap justify-center gap-2">
        {SHOTS.map((s) => (
          <button
            key={s.key}
            onClick={() => setActive(s.key)}
            className={cn(
              'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-[border-color,background-color,color]',
              active === s.key
                ? 'border-violet-500/50 bg-violet-500/12 text-violet-700 dark:text-violet-300'
                : 'border-border bg-card/50 text-muted-foreground backdrop-blur-xl hover:text-foreground',
            )}
          >
            <s.icon size={15} />
            {s.label}
          </button>
        ))}
      </div>

      {/* glass product frame — double-bezel: outer machined shell + inner display core */}
      <div
        data-frame
        className="relative mx-auto max-w-4xl rounded-[2rem] border border-border bg-card/40 p-2 shadow-[0_40px_120px_-40px_rgba(124,58,237,0.45),inset_0_1px_0_0_oklch(1_0_0/0.1)] backdrop-blur-2xl backdrop-saturate-150"
      >
        <div className="overflow-hidden rounded-[calc(2rem-0.5rem)] border border-border bg-background shadow-[inset_0_1px_1px_0_oklch(1_0_0/0.06)]">
          {/* window chrome */}
          <div className="flex items-center gap-1.5 border-b border-border px-5 py-3">
            <span className="size-3 rounded-full bg-muted-foreground/30" />
            <span className="size-3 rounded-full bg-muted-foreground/30" />
            <span className="size-3 rounded-full bg-muted-foreground/30" />
            <span className="ml-3 text-xs text-muted-foreground">app.one-ai.com/{current.key}</span>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={current.key}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="p-5"
            >
              <ShotOrMock shot={current} />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  )
}

/** Renders the real screenshot if present; otherwise a themed CSS mock. */
function ShotOrMock({ shot }: { shot: Shot }) {
  const [failed, setFailed] = useState(false)

  if (!failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={shot.src}
        alt={shot.alt}
        width={shot.width}
        height={shot.height}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
        className="h-auto w-full rounded-xl border border-border"
      />
    )
  }
  return <DashboardMock />
}

function DashboardMock() {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: <Bot size={16} />, title: 'Support Agent', meta: 'running · 24 tools', active: true },
          { icon: <Wrench size={16} />, title: 'Data Connector', meta: 'healthy · Databricks' },
          { icon: <Activity size={16} />, title: 'Live traces', meta: '92.4k today' },
        ].map((tile, i) => (
          <motion.div
            key={tile.title}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
          >
            <MockTile icon={tile.icon} title={tile.title} meta={tile.meta} active={tile.active} />
          </motion.div>
        ))}
      </div>
      <div className="mt-4 space-y-2.5">
        {['Plan', 'Call tool · search_docs', 'Synthesize answer', 'Verify & respond'].map((step, i) => (
          <motion.div
            key={step}
            initial={{ opacity: 0, x: -16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.08 }}
            className="flex items-center gap-3 rounded-xl border border-border bg-card/50 px-4 py-2.5"
          >
            <CheckCircle2 size={15} className="shrink-0 text-violet-500" />
            <span className="text-sm text-foreground/80">{step}</span>
            <span className="ml-auto font-mono text-xs text-muted-foreground">{(120 + i * 95).toString()}ms</span>
          </motion.div>
        ))}
      </div>
    </>
  )
}

function MockTile({
  icon,
  title,
  meta,
  active,
}: {
  icon: React.ReactNode
  title: string
  meta: string
  active?: boolean
}) {
  return (
    <div className={cn('rounded-xl border bg-card/50 p-4', active ? 'border-violet-500/50 glow-violet-sm' : 'border-border')}>
      <span className="flex size-8 items-center justify-center rounded-lg bg-violet-500/12 text-violet-600 dark:text-violet-400">
        {icon}
      </span>
      <p className="mt-3 text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{meta}</p>
    </div>
  )
}
