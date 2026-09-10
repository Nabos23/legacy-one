'use client'

import { motion, type Variants } from 'motion/react'
import {
  Bot,
  Wrench,
  Activity,
  Database,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react'
import { SectionHeading } from './section-heading'

const FEATURES = [
  {
    icon: Bot,
    title: 'Agent Studio',
    body: 'Design, version and deploy autonomous agents with a visual builder and battle-tested templates.',
  },
  {
    icon: Wrench,
    title: 'Tool Registry',
    body: 'Register your own APIs and functions as tools once, then share them across every agent. Distinct from Connectors (SaaS logins) and MCP servers (protocol-based tool sources).',
  },
  {
    icon: Activity,
    title: 'Live Tracing',
    body: 'Inspect every step, token and tool call in real time with full distributed traces.',
  },
  {
    icon: Database,
    title: 'Data Connections',
    body: 'Wire agents to your databases and vector stores with schema-aware, governed access.',
  },
  {
    icon: ShieldCheck,
    title: 'Governance & RBAC',
    body: 'Multi-tenant org controls, role-based access and guardrails that keep agents on policy.',
  },
  {
    icon: TerminalSquare,
    title: 'Playground',
    body: 'Prototype prompts and tool flows side-by-side, then promote what works to production.',
  },
]

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09 } },
}
const item: Variants = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
}

export function Features() {
  return (
    <section id="features" className="relative mx-auto max-w-6xl scroll-mt-24 px-4 py-24">
      <SectionHeading
        title="One control plane for every agent"
        subtitle="From first prototype to production fleet. Build, observe and govern AI agents without stitching together a dozen tools."
      />

      <motion.div
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: '0px 0px -10% 0px' }}
        className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        {FEATURES.map((f) => (
          <motion.div
            key={f.title}
            variants={item}
            className="group glass-card glass-interactive rounded-2xl border border-border bg-card/50 p-6 backdrop-blur-2xl backdrop-saturate-150"
          >
            <span className="mb-4 flex size-11 items-center justify-center rounded-xl bg-violet-500/12 text-violet-600 transition-colors group-hover:bg-violet-500/20 dark:text-violet-400">
              <f.icon size={20} />
            </span>
            <h3 className="text-base font-semibold text-foreground">{f.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  )
}
