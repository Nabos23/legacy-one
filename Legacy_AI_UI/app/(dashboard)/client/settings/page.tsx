'use client'

import { useState } from 'react'
import { User, ShieldCheck, Bell, Plug, AlertTriangle } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { Reveal } from '@/components/ui/reveal'
import { ProfileSection } from '@/components/settings/profile-section'
import { SecuritySection } from '@/components/settings/security-section'
import { NotificationsSection } from '@/components/settings/notifications-section'
import { AppearanceSection } from '@/components/settings/appearance-section'
import { ConnectionsSection, useConnectedCount } from '@/components/settings/connections-section'
import { DangerSection } from '@/components/settings/danger-section'
import { cn } from '@/lib/utils'
import { CLIENT_LANDING_PATHS } from '@/lib/auth-cookies'

const PREFS_KEY = 'oneai:client-prefs'

const LANDING_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  agents: 'Agents',
  playground: 'Playground',
  tracing: 'Observability',
}
const CLIENT_LANDING_OPTIONS = CLIENT_LANDING_PATHS.map(p => ({ value: p, label: LANDING_LABELS[p] }))

const SECTIONS = [
  { key: 'profile', label: 'Profile', icon: User },
  { key: 'security', label: 'Security', icon: ShieldCheck },
  { key: 'notifications', label: 'Notifications', icon: Bell },
  { key: 'connections', label: 'Connected Accounts', icon: Plug },
  { key: 'danger', label: 'Danger Zone', icon: AlertTriangle },
] as const

type SectionKey = (typeof SECTIONS)[number]['key']

export default function SettingsPage() {
  const [section, setSection] = useState<SectionKey>('profile')
  const connectedCount = useConnectedCount()

  return (
    <>
      <Reveal>
        <PageHeader title="Settings" description="Manage your account and preferences" />
      </Reveal>

      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6 items-start">
        <Reveal delay={40}>
          <nav className="glass-card rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-2xl backdrop-saturate-150 p-2 lg:sticky lg:top-20">
            <div className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible">
              {SECTIONS.map(s => {
                const active = section === s.key
                const danger = s.key === 'danger'
                return (
                  <button
                    key={s.key}
                    type="button"
                    onClick={() => setSection(s.key)}
                    className={cn(
                      'flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-[13.5px] font-medium whitespace-nowrap transition-colors shrink-0',
                      active
                        ? danger
                          ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                          : 'bg-violet-500/10 text-violet-600 dark:text-violet-400'
                        : 'text-[var(--text-3)] hover:bg-[var(--surface-2)] hover:text-[var(--text-1)]',
                    )}
                  >
                    <s.icon className="w-4 h-4 shrink-0" />
                    {s.label}
                    {s.key === 'connections' && connectedCount > 0 && (
                      <Badge variant={active ? 'primary' : 'neutral'} className="ml-auto">
                        {connectedCount}
                      </Badge>
                    )}
                  </button>
                )
              })}
            </div>
          </nav>
        </Reveal>

        <div className="space-y-5 min-w-0">
          {section === 'profile' && (
            <Reveal delay={80}>
              <ProfileSection />
            </Reveal>
          )}
          {section === 'security' && (
            <Reveal delay={80}>
              <SecuritySection />
            </Reveal>
          )}
          {section === 'notifications' && (
            <Reveal delay={80} className="space-y-5">
              <AppearanceSection landingOptions={CLIENT_LANDING_OPTIONS} />
              <NotificationsSection storageKey={PREFS_KEY} />
            </Reveal>
          )}
          {section === 'connections' && (
            <Reveal delay={80}>
              <ConnectionsSection manageHref="/client/connectors" />
            </Reveal>
          )}
          {section === 'danger' && (
            <Reveal delay={80}>
              <DangerSection />
            </Reveal>
          )}
        </div>
      </div>
    </>
  )
}
