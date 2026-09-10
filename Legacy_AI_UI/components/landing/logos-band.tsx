'use client'

import { VelocityMarquee } from './velocity-marquee'

const KEYWORDS = [
  'Agent Orchestration',
  'Tool Registry',
  'Observability',
  'Tracing',
  'Multi-tenant',
  'RBAC',
  'Vector Memory',
  'Playground',
  'Guardrails',
  'Analytics',
]

export function LogosBand() {
  return (
    <section className="border-y border-border bg-card/60 py-6">
      <p className="mb-4 text-center text-sm text-muted-foreground">
        Everything your agents need, in one place
      </p>
      <VelocityMarquee baseVelocity={2.5}>
        {KEYWORDS.map((k) => (
          <span
            key={k}
            className="mx-3 inline-flex items-center rounded-full border border-border bg-card/60 px-4 py-2 text-sm font-semibold text-foreground/80 backdrop-blur-xl"
          >
            {k}
          </span>
        ))}
      </VelocityMarquee>
    </section>
  )
}
