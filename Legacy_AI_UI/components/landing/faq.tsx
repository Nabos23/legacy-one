'use client'

import { useState } from 'react'
import { motion } from 'motion/react'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { SectionHeading } from './section-heading'

const FAQS = [
  {
    q: 'What exactly is ONE-AI?',
    a: 'A single control plane to build, connect, observe and govern autonomous AI agents, from your first prototype to a production fleet across your whole organization.',
  },
  {
    q: 'Which models and tools can I connect?',
    a: 'Any major LLM provider plus your own endpoints, alongside databases, vector stores and SaaS tools. Everything lives in a governed registry so every agent can reuse it.',
  },
  {
    q: 'Is my data used to train models?',
    a: 'Never. You bring your own keys and your data stays yours. It is not used to train any shared model.',
  },
  {
    q: 'How do you handle security and compliance?',
    a: 'Role-based access control, org-scoped multi-tenancy, audit logs, SSO/SAML and SOC 2 controls are built in, not bolted on later.',
  },
  {
    q: 'Can I try it for free?',
    a: 'Yes. The Starter plan is free forever, and Team includes a 14-day trial with no credit card required.',
  },
]

export function Faq() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="relative mx-auto max-w-3xl scroll-mt-24 px-4 py-24">
      <SectionHeading title="Questions, answered" />

      <div className="mt-12 space-y-3">
        {FAQS.map((f, i) => {
          const isOpen = open === i
          return (
            <motion.div
              key={f.q}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.05 }}
              className="glass-card overflow-hidden rounded-2xl border border-border bg-card/50 backdrop-blur-2xl backdrop-saturate-150"
            >
              <button
                onClick={() => setOpen(isOpen ? null : i)}
                aria-expanded={isOpen}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
              >
                <span className="text-sm font-semibold text-foreground sm:text-base">{f.q}</span>
                <Plus
                  size={18}
                  className={cn(
                    'shrink-0 text-violet-500 transition-transform duration-300',
                    isOpen && 'rotate-45',
                  )}
                />
              </button>
              <div
                className={cn(
                  'grid transition-[grid-template-rows] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]',
                  isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
                )}
              >
                <div className="overflow-hidden">
                  <p className="px-5 pb-5 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </section>
  )
}
