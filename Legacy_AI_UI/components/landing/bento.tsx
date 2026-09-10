'use client'

import { motion, type Variants } from 'motion/react'
import { Boxes, ShieldCheck, Lock, Workflow, ArrowRight, Wrench, Database, Bot } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useGsapScroll } from '@/hooks/use-gsap-scroll'
import { SectionHeading } from './section-heading'

const tile: Variants = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
}

const INTEGRATIONS = [
  'OpenAI', 'Anthropic', 'Databricks', 'Slack', 'GitHub', 'Snowflake',
  'Pinecone', 'Qdrant', 'AWS', 'Notion', 'Stripe', 'Zapier',
]

const COMPLIANCE = ['SOC 2 Type II', 'GDPR', 'HIPAA', 'SSO / SAML', 'SCIM', 'Audit logs']

const PIPELINE = ['Trigger', 'Agent', 'Tool', 'Review']
const PRIVACY_STEPS = ['Bring your own keys', 'Encrypted at rest & in transit', 'Never used to train models']

function TileShell({
  className,
  children,
  depth,
  emphasis,
}: {
  className?: string
  children: React.ReactNode
  depth?: number
  /** Primary tile in the grid — gets the stronger border/glow treatment. */
  emphasis?: boolean
}) {
  return (
    <motion.div
      variants={tile}
      data-parallax={depth}
      className={cn(
        'glass-card glass-interactive rounded-3xl border p-7 backdrop-blur-2xl backdrop-saturate-150',
        emphasis
          ? 'border-violet-500/30 bg-card/60 glow-violet-sm'
          : 'border-border bg-card/50',
        className,
      )}
    >
      {children}
    </motion.div>
  )
}

/** Small labelled stepper — reused for both the workflow pipeline and the
 * privacy steps so the two same-row tiles share the same visual rhythm
 * instead of one being packed and the other mostly empty. */
function Stepper({ steps }: { steps: string[] }) {
  return (
    <div className="mt-4 flex flex-col">
      {steps.map((step, i) => (
        <div key={step} className="flex flex-col">
          <span className="inline-flex w-fit items-center gap-2 rounded-lg border border-border bg-background/60 px-2.5 py-1.5 text-xs font-medium text-foreground/80">
            <span className="size-1.5 shrink-0 rounded-full bg-violet-500" />
            {step}
          </span>
          {i < steps.length - 1 && <span className="my-1 ml-[11px] h-2.5 w-px bg-border" />}
        </div>
      ))}
    </div>
  )
}

export function Bento() {
  // Depth-layered drift, same convention as Hero/Showcase: background glow +
  // grid move slowest, each tile drifts at its own rate as the section
  // scrolls through the viewport — a bento grid with real depth instead of
  // a flat, static wall of cards.
  const scope = useGsapScroll<HTMLDivElement>((gsap, _ST, el) => {
    gsap.utils.toArray<HTMLElement>(el.querySelectorAll('[data-parallax]')).forEach((node) => {
      const depth = Number(node.dataset.parallax) || 0.3
      gsap.to(node, {
        yPercent: -22 * depth,
        ease: 'none',
        scrollTrigger: { trigger: el, start: 'top bottom', end: 'bottom top', scrub: true },
      })
    })
  })

  return (
    <section ref={scope} className="relative mx-auto max-w-6xl overflow-hidden px-4 py-24">
      <SectionHeading
        eyebrow="Built for scale"
        title="Enterprise-grade by default"
        subtitle="The guardrails, integrations and observability you need to run agents in production. No glue code required."
      />

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: '0px 0px -10% 0px' }}
        transition={{ staggerChildren: 0.08 }}
        className="relative z-10 mt-14 grid grid-cols-1 gap-4 md:grid-cols-4"
      >
        {/* Integrations — tall feature tile */}
        <TileShell depth={0.1} emphasis className="flex flex-col md:col-span-2 md:row-span-2">
          <span className="mb-4 inline-flex size-11 items-center justify-center rounded-xl bg-violet-500/12 text-violet-600 dark:text-violet-400">
            <Boxes size={20} />
          </span>
          <h3 className="text-xl font-bold text-foreground">Plug into your whole stack</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            Connect models, data stores and SaaS tools through a governed registry.
            Add your own with a few lines and every agent can use them instantly.
          </p>

          {/* mini flow diagram: tools -> registry -> agent */}
          <div className="mt-6 flex items-center gap-3 rounded-2xl border border-border bg-background/50 px-4 py-3.5">
            <div className="flex items-center -space-x-2">
              <span className="flex size-8 items-center justify-center rounded-full border border-border bg-card text-foreground/70">
                <Wrench size={13} />
              </span>
              <span className="flex size-8 items-center justify-center rounded-full border border-border bg-card text-foreground/70">
                <Database size={13} />
              </span>
              <span className="flex size-8 items-center justify-center rounded-full border border-border bg-card text-foreground/70">
                <Boxes size={13} />
              </span>
            </div>
            <span className="h-px flex-1 bg-border" aria-hidden />
            <span className="shrink-0 rounded-lg border border-violet-500/40 bg-violet-500/10 px-2.5 py-1.5 text-xs font-semibold text-violet-600 dark:text-violet-300">
              Tool Registry
            </span>
            <span className="h-px flex-1 bg-border" aria-hidden />
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-violet-600 text-white">
              <Bot size={14} />
            </span>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {INTEGRATIONS.map((name) => (
              <span
                key={name}
                className="rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-medium text-foreground/80 backdrop-blur-xl"
              >
                {name}
              </span>
            ))}
            <span className="inline-flex items-center gap-1 rounded-full border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-xs font-semibold text-violet-600 dark:text-violet-300">
              +120 more <ArrowRight size={12} />
            </span>
          </div>
        </TileShell>

        {/* Compliance — badge wall */}
        <TileShell depth={0.25} className="md:col-span-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-foreground">Compliant out of the box</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Security controls your auditors already trust, with no retrofitting.
              </p>
            </div>
            <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/12 text-violet-600 dark:text-violet-400">
              <ShieldCheck size={18} />
            </span>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {COMPLIANCE.map((c) => (
              <span
                key={c}
                className="rounded-lg border border-border bg-background/60 px-2.5 py-1 text-xs font-semibold text-foreground/75"
              >
                {c}
              </span>
            ))}
          </div>
        </TileShell>

        {/* Privacy — statement tile */}
        <TileShell depth={0.4} className="flex flex-col md:col-span-1">
          <span className="mb-4 inline-flex size-10 items-center justify-center rounded-xl bg-violet-500/12 text-violet-600 dark:text-violet-400">
            <Lock size={18} />
          </span>
          <h3 className="text-base font-semibold text-foreground">Private by design</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
            Your data never trains anyone else’s model.
          </p>
          <Stepper steps={PRIVACY_STEPS} />
          <span className="mt-4 inline-flex w-fit items-center gap-1.5 rounded-full bg-violet-500/10 px-3 py-1 text-xs font-semibold text-violet-600 dark:text-violet-300">
            <span className="size-1.5 rounded-full bg-violet-500" /> Zero data retention
          </span>
        </TileShell>

        {/* Workflows — vertical pipeline stepper */}
        <TileShell depth={0.4} className="flex flex-col md:col-span-1">
          <span className="mb-4 inline-flex size-10 items-center justify-center rounded-xl bg-violet-500/12 text-violet-600 dark:text-violet-400">
            <Workflow size={18} />
          </span>
          <h3 className="text-base font-semibold text-foreground">Deterministic workflows</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
            Chain agents and tools into observable, repeatable pipelines.
          </p>
          <Stepper steps={PIPELINE} />
        </TileShell>
      </motion.div>
    </section>
  )
}
