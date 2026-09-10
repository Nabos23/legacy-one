'use client'

import { Star } from 'lucide-react'
import { VelocityMarquee } from './velocity-marquee'
import { SectionHeading } from './section-heading'

type Quote = { quote: string; name: string; role: string; initials: string }

// PLACEHOLDER — fictional names/companies, swap for real customer quotes before launch.
const QUOTES: Quote[] = [
  { quote: 'We shipped our first production agent in a weekend. The tracing alone paid for itself.', name: 'Maya Chen', role: 'VP Eng, Northwind', initials: 'MC' },
  { quote: 'Finally a control plane our security team signed off on. RBAC and audit logs were day-one.', name: 'David Okafor', role: 'CISO, Aperture', initials: 'DO' },
  { quote: 'The playground-to-production flow cut our iteration time by 30x. Not an exaggeration.', name: 'Sofia Ramos', role: 'ML Lead, Lumen', initials: 'SR' },
  { quote: 'Tool registry means every team reuses the same governed integrations. No more glue code.', name: 'Tom Reed', role: 'Staff Eng, Kestrel', initials: 'TR' },
  { quote: 'We replaced three internal tools with ONE-AI and our agents are more reliable for it.', name: 'Priya Nair', role: 'Director, Helix', initials: 'PN' },
]

export function Testimonials() {
  return (
    <section className="relative overflow-hidden py-24">
      <SectionHeading
        eyebrow="Loved by teams"
        title="Trusted to run agents in production"
        subtitle="From scrappy startups to regulated enterprises."
        className="px-4"
      />

      <div className="mt-14">
        <VelocityMarquee baseVelocity={2}>
          {QUOTES.map((q) => (
            <QuoteCard key={q.name} {...q} />
          ))}
        </VelocityMarquee>
      </div>
    </section>
  )
}

function QuoteCard({ quote, name, role, initials }: Quote) {
  return (
    <figure className="glass-card mx-2 w-[min(340px,85vw)] shrink-0 rounded-2xl border border-border bg-card/50 p-6 backdrop-blur-2xl backdrop-saturate-150">
      <div className="mb-3 flex gap-0.5 text-violet-500">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star key={i} size={14} className="fill-violet-500" />
        ))}
      </div>
      <blockquote className="text-sm leading-relaxed text-foreground/90">“{quote}”</blockquote>
      <figcaption className="mt-4 flex items-center gap-3">
        <span className="flex size-9 items-center justify-center rounded-full bg-violet-500/15 text-xs font-bold text-violet-600 dark:text-violet-400">
          {initials}
        </span>
        <span className="flex flex-col">
          <span className="text-sm font-semibold text-foreground">{name}</span>
          <span className="text-xs text-muted-foreground">{role}</span>
        </span>
      </figcaption>
    </figure>
  )
}
