'use client'

import Link from 'next/link'
import {
  BookOpen,
  LifeBuoy,
  ExternalLink,
  Mail,
  Activity,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { Reveal } from '@/components/ui/reveal'
import { IconTile } from '@/components/ui/icon-tile'
import { SettingsCard, SettingsCardHeader } from '@/components/settings/settings-card'
import { HelpTopics } from '@/components/help/help-topics'
import { HelpFaqSection } from '@/components/help/help-faq'
import { Glossary } from '@/components/help/glossary'
import { useAuth } from '@/contexts/auth-context'
import { API_BASE_URL as API_URL } from '@/lib/config'
import { CLIENT_HELP_TOPICS, CLIENT_FAQS, GLOSSARY } from '@/lib/help-content'

const shortcuts = [
  { label: 'Open command palette', keys: '⌘K' },
  { label: 'Close modal / palette', keys: 'Esc' },
  { label: 'New line in chat', keys: '⇧⏎' },
  { label: 'Send message', keys: '⏎' },
]

const steps = [
  {
    title: 'Register your tools',
    description: 'Go to Tools and connect your first integration',
  },
  {
    title: 'Create an agent',
    description: 'Use the Agent Wizard to configure and deploy',
  },
  {
    title: 'Test in Playground',
    description: 'Chat with your agent and iterate on the prompt',
  },
]

export default function HelpPage() {
  const { user } = useAuth()

  return (
    <>
      <Reveal>
        <PageHeader title="Help & Documentation" description="Guides, references, and support for every part of ONE-AI" />
      </Reveal>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
        <Reveal delay={40}>
          <a
            href={`${API_URL}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="glass-card glass-hover block rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-2xl backdrop-saturate-150 p-6 h-full"
          >
            <IconTile icon={BookOpen} size="lg" className="mb-4" />
            <h3 className="text-[16px] font-semibold mb-2 text-[var(--text-1)]">API Reference</h3>
            <p className="text-[13px] text-[var(--text-3)] mb-4">
              Explore endpoints, schemas, and authentication for the ONE-AI API.
            </p>
            <span className="text-[13px] text-violet-600 dark:text-violet-400 flex items-center gap-1">
              Open Docs <ExternalLink className="w-4 h-4" />
            </span>
          </a>
        </Reveal>

        <Reveal delay={60}>
          <div className="glass-card rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-2xl backdrop-saturate-150 p-6 h-full">
            <IconTile icon={LifeBuoy} size="lg" color="info" className="mb-4" />
            <h3 className="text-[16px] font-semibold mb-2 text-[var(--text-1)]">Contact Support</h3>
            <p className="text-[13px] text-[var(--text-3)] mb-4">
              Need help? Reach out to your organization administrator.
            </p>
            <a href="mailto:admin@oneai.dev">
              <Button variant="secondary">
                <Mail className="w-4 h-4 mr-2" />
                Contact Admin
              </Button>
            </a>
          </div>
        </Reveal>
      </div>

      <Reveal delay={80} className="mb-5">
        <SettingsCard>
          <SettingsCardHeader
            icon={LifeBuoy}
            title="Getting Started"
            description="The fastest path from zero to your first working agent"
          />
          <div className="space-y-6">
            {steps.map((step, i) => (
              <div key={step.title} className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-violet-600 flex items-center justify-center text-[13px] font-semibold text-white shrink-0">
                  {i + 1}
                </div>
                <div>
                  <h4 className="text-[14px] font-semibold text-[var(--text-1)]">{step.title}</h4>
                  <p className="text-[13px] text-[var(--text-3)] mt-1">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
          <Link href="/client/agents/create" className="inline-block mt-6">
            <Button variant="primary" size="sm">Create your first agent →</Button>
          </Link>
        </SettingsCard>
      </Reveal>

      <Reveal delay={100} className="mb-5">
        <HelpTopics topics={CLIENT_HELP_TOPICS} />
      </Reveal>

      <Reveal delay={120} className="mb-5">
        <HelpFaqSection faqs={CLIENT_FAQS} />
      </Reveal>

      <Reveal delay={140} className="mb-5">
        <Glossary terms={GLOSSARY} />
      </Reveal>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Reveal delay={160}>
          <SettingsCard>
            <h3 className="text-[16px] font-semibold mb-4 text-[var(--text-1)]">Keyboard Shortcuts</h3>
            <div className="space-y-3">
              {shortcuts.map(s => (
                <div key={s.label} className="flex items-center justify-between text-[13px]">
                  <span className="text-[var(--text-2)]">{s.label}</span>
                  <kbd className="bg-[var(--surface-2)] border border-[var(--border)] px-2 py-1 rounded font-mono text-[11px] text-[var(--text-1)]">
                    {s.keys}
                  </kbd>
                </div>
              ))}
            </div>
          </SettingsCard>
        </Reveal>

        <Reveal delay={180}>
          <SettingsCard>
            <h3 className="text-[16px] font-semibold mb-4 text-[var(--text-1)]">System Info</h3>
            <div className="space-y-0 text-[12px] font-mono">
              {[
                ['Platform', 'ONE-AI v1.0.0'],
                ['API', API_URL],
                ['Region', 'eu-west-1'],
                ['Org', user?.organization_id ?? '—'],
                ['Account', user?.email ?? '—'],
              ].map(([key, val], i, arr) => (
                <div
                  key={key}
                  className={`flex justify-between py-2 ${i < arr.length - 1 ? 'border-b border-[var(--border)]' : ''}`}
                >
                  <span className="text-[var(--text-3)]">{key}</span>
                  <span className="text-[var(--text-2)] truncate ml-4 max-w-[60%] text-right">{val}</span>
                </div>
              ))}
            </div>
            <a href={`${API_URL}/health`} target="_blank" rel="noopener noreferrer" className="inline-block mt-4">
              <Button variant="ghost" size="xs">
                <Activity className="w-4 h-4 mr-1" />
                Check API Status
              </Button>
            </a>
          </SettingsCard>
        </Reveal>
      </div>
    </>
  )
}
