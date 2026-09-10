'use client'

import { motion, type Variants } from 'motion/react'
import { Plug, ShieldCheck, Bot, Server } from 'lucide-react'
import { ConnectorLogo } from '@/components/connectors/connector-logo'
import { SectionHeading } from './section-heading'
import { VelocityMarquee } from './velocity-marquee'

const ROW_1 = [
  'slack', 'gmail', 'notion', 'github', 'hubspot', 'google-drive',
  'jira', 'salesforce', 'stripe', 'shopify', 'zendesk', 'airtable',
]

const ROW_2 = [
  'google-sheets', 'dropbox', 'teams', 'linkedin', 'mailchimp', 'docusign',
  'quickbooks', 'figma', 'twilio', 'sentry', 'datadog', 'confluence',
]

const CAPABILITIES = [
  {
    icon: Plug,
    title: 'Connect once, use everywhere',
    body: 'Authenticate a service with OAuth or an API key, and every agent in your org can use it. No per-agent setup.',
  },
  {
    icon: Bot,
    title: 'Real actions, not just data',
    body: 'Connectors are exposed to agents as callable tools, so they can send a message, update a record or file a ticket, not just read one.',
  },
  {
    icon: ShieldCheck,
    title: 'Scoped and revocable',
    body: 'Credentials live at the user or org level, only run for connectors you explicitly attach to an agent, and can be disconnected at any time.',
  },
  {
    icon: Server,
    title: 'Native MCP support',
    body: 'Point an agent at any Model Context Protocol server and its tools show up alongside your connectors. No custom integration required.',
  },
]

const item: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
}

export function Connectors() {
  return (
    <section id="connectors" className="relative mx-auto max-w-6xl scroll-mt-24 px-4 py-24">
      <SectionHeading
        title="Give your agents hands, not just eyes"
        subtitle="Connect the tools your team already uses and let agents act on them directly: send, update, file, post, all under your control."
      />

      <div className="mt-12 -mx-4 space-y-3 [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
        <VelocityMarquee baseVelocity={1.6}>
          {ROW_1.map((id, i) => (
            <span key={`${id}-${i}`} className="mx-2.5 inline-flex">
              <ConnectorLogo providerId={id} size="lg" />
            </span>
          ))}
        </VelocityMarquee>
        <VelocityMarquee baseVelocity={-1.6}>
          {ROW_2.map((id, i) => (
            <span key={`${id}-${i}`} className="mx-2.5 inline-flex">
              <ConnectorLogo providerId={id} size="lg" />
            </span>
          ))}
        </VelocityMarquee>
      </div>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        55+ connectors across email, chat, CRM, storage, dev tools, finance and support, with more added regularly.
      </p>

      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: '0px 0px -10% 0px' }}
        transition={{ staggerChildren: 0.09 }}
        className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        {CAPABILITIES.map((c) => (
          <motion.div
            key={c.title}
            variants={item}
            className="glass-card rounded-2xl border border-border bg-card/50 p-6 backdrop-blur-2xl backdrop-saturate-150"
          >
            <span className="mb-4 flex size-11 items-center justify-center rounded-xl bg-violet-500/12 text-violet-600 dark:text-violet-400">
              <c.icon size={20} />
            </span>
            <h3 className="text-base font-semibold text-foreground">{c.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{c.body}</p>
          </motion.div>
        ))}
      </motion.div>
    </section>
  )
}
