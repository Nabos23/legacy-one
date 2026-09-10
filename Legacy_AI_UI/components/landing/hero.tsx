'use client'

import Link from 'next/link'
import { motion, useMotionTemplate, useReducedMotion, useScroll, useTransform, type Variants } from 'motion/react'
import { ArrowRight, Bot, CheckCircle2, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useGsapScroll } from '@/hooks/use-gsap-scroll'
import { Magnetic } from './magnetic'

const HEADLINE = ['Build,', 'orchestrate', 'and', 'scale', 'AI', 'agents.']

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.15 } },
}
const word: Variants = {
  hidden: { y: '110%', opacity: 0 },
  show: { y: '0%', opacity: 1, transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] } },
}

export function Hero() {
  // Parallax on floating cards + glow blobs as the hero scrolls out.
  const scope = useGsapScroll<HTMLDivElement>((gsap, _ST, el) => {
    gsap.utils.toArray<HTMLElement>(el.querySelectorAll('[data-parallax]')).forEach((node) => {
      const depth = Number(node.dataset.parallax) || 0.3
      gsap.to(node, {
        yPercent: -22 * depth,
        ease: 'none',
        scrollTrigger: { trigger: el, start: 'top top', end: 'bottom top', scrub: true },
      })
    })
  })

  const reducedMotion = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: scope, offset: ['start start', 'end start'] })
  const opacity = useTransform(scrollYProgress, [0, 0.65], [1, 0])
  const contentY = useTransform(scrollYProgress, [0, 1], reducedMotion ? [0, 0] : [0, 120])
  const scale = useTransform(scrollYProgress, [0, 1], reducedMotion ? [1, 1] : [1, 0.94])
  const contentTransform = useMotionTemplate`translateY(${contentY}px) scale(${scale})`

  return (
    <section
      ref={scope}
      className="relative flex min-h-[100svh] items-center justify-center overflow-x-clip px-4 pt-28 pb-20"
    >
      <div className="pointer-events-none absolute inset-0 bg-dots text-foreground/[0.16] dark:text-foreground/[0.13]" />
      <div className="pointer-events-none absolute inset-0 bg-noise opacity-60" />
      <div
        data-parallax="0.5"
        className="sentry-block gpu-layer pointer-events-none absolute -top-24 left-1/2 size-[34rem] -translate-x-1/2 rounded-full bg-violet-500/15 blur-[120px]"
      />
      <div
        data-parallax="0.25"
        className="sentry-block gpu-layer pointer-events-none absolute -bottom-32 right-[12%] size-[26rem] rounded-full bg-violet-500/10 blur-[120px]"
      />

      <motion.div
        style={{ opacity, transform: contentTransform }}
        className="relative z-10 mx-auto max-w-3xl text-center"
      >
        <motion.span
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-xl"
        >
          The enterprise AI agent platform
        </motion.span>

        <motion.h1
          aria-label={HEADLINE.join(' ')}
          variants={container}
          initial="hidden"
          animate="show"
          className="mt-6 flex flex-wrap justify-center gap-x-3 gap-y-1 text-4xl font-extrabold leading-[1.05] tracking-tight text-foreground sm:text-6xl"
        >
          {HEADLINE.map((w, i) => (
            <span key={i} aria-hidden className="overflow-hidden py-1">
              <motion.span
                variants={word}
                className={
                  w === 'agents.' ? 'inline-block text-violet-600 dark:text-violet-400' : 'inline-block'
                }
              >
                {w}
              </motion.span>
            </span>
          ))}
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.7 }}
          className="mx-auto mt-6 max-w-xl text-base text-muted-foreground sm:text-lg"
        >
          One control plane to design, connect tools, trace, and govern autonomous
          AI agents across your whole organization, securely and at scale.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.85 }}
          className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <Magnetic>
            <Button
              variant="primary"
              size="lg"
              className="group h-11 pl-5 pr-1.5 text-sm"
              nativeButton={false}
              render={<Link href="/register" />}
            >
              Get started free
              <span className="ml-1 flex size-7 items-center justify-center rounded-full bg-white/15 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-0.5">
                <ArrowRight size={14} />
              </span>
            </Button>
          </Magnetic>
          <Magnetic strength={0.25}>
            <Button
              variant="outline"
              size="lg"
              className="h-11 px-5 text-sm"
              nativeButton={false}
              render={<Link href="/login" />}
            >
              Log in
            </Button>
          </Magnetic>
        </motion.div>
      </motion.div>

      {/* floating glass elements */}
      <FloatingCard
        className="left-[6%] top-[26%] hidden lg:flex"
        depth={0.6}
        icon={<Bot size={16} className="text-violet-500" />}
        label="Active agents"
        value="1,284"
      />
      <FloatingCard
        className="right-[7%] top-[34%] hidden lg:flex"
        depth={0.35}
        icon={<Zap size={16} className="text-violet-500" />}
        label="Tasks / day"
        value="92.4k"
      />
      <div
        data-parallax="0.8"
        className="glass-card absolute right-[16%] top-[68%] z-10 hidden animate-floatY items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-2 text-xs font-medium text-foreground/85 backdrop-blur-2xl lg:flex"
      >
        <CheckCircle2 size={14} className="text-emerald-500" />
        Trace completed · 312ms
      </div>
    </section>
  )
}

function FloatingCard({
  className,
  depth,
  icon,
  label,
  value,
}: {
  className?: string
  depth: number
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div
      data-parallax={depth}
      className={`glass-card absolute z-10 animate-floatY items-center gap-3 rounded-2xl border border-border bg-card/60 px-4 py-3 backdrop-blur-2xl backdrop-saturate-150 ${className ?? ''}`}
    >
      <span className="flex size-9 items-center justify-center rounded-xl bg-violet-500/12">{icon}</span>
      <span className="flex flex-col text-left">
        <span className="text-lg font-bold leading-none text-foreground">{value}</span>
        <span className="text-xs text-muted-foreground">{label}</span>
      </span>
    </div>
  )
}
