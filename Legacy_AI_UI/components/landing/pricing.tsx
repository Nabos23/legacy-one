'use client'

import Link from 'next/link'
import { motion, type Variants } from 'motion/react'
import { Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { SectionHeading } from './section-heading'

type Tier = {
  name: string
  price: string
  cadence?: string
  blurb: string
  features: string[]
  cta: string
  href: string
  featured?: boolean
}

const TIERS: Tier[] = [
  {
    name: 'Starter',
    price: '$0',
    cadence: '/mo',
    blurb: 'For solo builders prototyping their first agents.',
    features: ['1 workspace', 'Up to 3 agents', 'Playground & tracing', 'Community support'],
    cta: 'Start free',
    href: '/register',
  },
  {
    name: 'Team',
    price: '$49',
    cadence: '/user/mo',
    blurb: 'For teams shipping agents to production.',
    features: ['Unlimited agents', 'Tool registry & data connections', 'Live tracing & analytics', 'RBAC & audit logs', 'Priority support'],
    cta: 'Start 14-day trial',
    href: '/register',
    featured: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    blurb: 'For regulated orgs running agent fleets at scale.',
    features: ['SSO / SAML & SCIM', 'Bring your own keys', 'Dedicated infrastructure', 'SOC 2 & DPA', 'Solutions engineering'],
    cta: 'Contact sales',
    href: '/register',
  },
]

const card: Variants = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
}

export function Pricing() {
  return (
    <section id="pricing" className="relative mx-auto max-w-6xl scroll-mt-24 px-4 py-24">
      <SectionHeading
        title="Start free, scale when you’re ready"
        subtitle="No credit card to start. Upgrade the moment you outgrow it."
      />

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: '0px 0px -10% 0px' }}
        transition={{ staggerChildren: 0.1 }}
        className="mt-14 grid gap-5 lg:grid-cols-3"
      >
        {TIERS.map((t) => (
          <motion.div
            key={t.name}
            variants={card}
            className={cn(
              'glass-card relative flex flex-col rounded-3xl border p-7 backdrop-blur-2xl backdrop-saturate-150',
              t.featured
                ? 'border-violet-500/50 bg-card/70 glow-violet lg:-mt-4 lg:mb-0'
                : 'glass-interactive border-border bg-card/50',
            )}
          >
            {t.featured && (
              <span className="absolute right-6 top-6 rounded-full bg-violet-600 px-3 py-1 text-xs font-semibold text-white">
                Most popular
              </span>
            )}
            <h3 className="text-base font-semibold text-foreground">{t.name}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{t.blurb}</p>
            <div className="mt-5 flex items-end gap-1">
              <span className="text-4xl font-extrabold tracking-tight text-foreground">{t.price}</span>
              {t.cadence && <span className="mb-1 text-sm text-muted-foreground">{t.cadence}</span>}
            </div>

            <ul className="mt-6 flex-1 space-y-3">
              {t.features.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-sm text-foreground/85">
                  <Check size={16} className="mt-0.5 shrink-0 text-violet-500" />
                  {f}
                </li>
              ))}
            </ul>

            <Button
              variant={t.featured ? 'primary' : 'outline'}
              size="lg"
              className="mt-8 h-11 w-full text-sm"
              nativeButton={false}
              render={<Link href={t.href} />}
            >
              {t.cta}
            </Button>
          </motion.div>
        ))}
      </motion.div>
    </section>
  )
}
