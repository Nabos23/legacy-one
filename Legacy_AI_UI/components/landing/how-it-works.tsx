'use client'

import { motion } from 'motion/react'
import { useGsapScroll } from '@/hooks/use-gsap-scroll'
import { SectionHeading } from './section-heading'

const STEPS = [
  {
    n: '01',
    title: 'Connect your stack',
    body: 'Register tools, databases and APIs in a governed registry once, for every agent.',
  },
  {
    n: '02',
    title: 'Compose an agent',
    body: 'Assemble prompts, tools and memory in Agent Studio, then test instantly in the playground.',
  },
  {
    n: '03',
    title: 'Trace & refine',
    body: 'Watch every token and tool call in live traces, catch regressions and tune behaviour.',
  },
  {
    n: '04',
    title: 'Ship & govern',
    body: 'Promote to production with RBAC, guardrails and org-wide analytics from day one.',
  },
]

export function HowItWorks() {
  const scope = useGsapScroll<HTMLDivElement>((gsap, _ST, el) => {
    const fill = el.querySelector('[data-progress-fill]')
    if (!fill) return
    gsap.fromTo(
      fill,
      { scaleY: 0 },
      {
        scaleY: 1,
        ease: 'none',
        transformOrigin: 'top',
        scrollTrigger: {
          trigger: el,
          start: 'top 60%',
          end: 'bottom 80%',
          scrub: true,
        },
      },
    )
  })

  return (
    <section
      id="how-it-works"
      ref={scope}
      className="relative mx-auto max-w-6xl scroll-mt-24 px-4 py-24"
    >
      <SectionHeading title="From idea to production fleet" />

      <div className="mt-14 grid gap-10 md:grid-cols-[auto_1fr]">
        {/* scrubbed progress rail */}
        <div className="relative hidden w-1 justify-self-center rounded-full bg-border md:block">
          <span
            data-progress-fill
            className="absolute inset-x-0 top-0 h-full origin-top scale-y-0 rounded-full bg-violet-600"
          />
        </div>

        <div className="flex flex-col gap-5">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.n}
              initial={{ opacity: 0, x: 32 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '0px 0px -15% 0px' }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: i * 0.05 }}
              className="flex items-start gap-5 rounded-2xl border border-border bg-card/50 p-6 backdrop-blur-2xl backdrop-saturate-150"
            >
              <span className="text-2xl font-extrabold tabular-nums text-violet-600/90 dark:text-violet-400/90">
                {s.n}
              </span>
              <div>
                <h3 className="text-lg font-semibold text-foreground">{s.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
