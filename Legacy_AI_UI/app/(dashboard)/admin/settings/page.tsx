'use client'

import { useState, useEffect } from 'react'
import { Save, Settings2, ShieldCheck, User, Bell, Plug, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { Separator } from '@/components/ui/separator'
import { InfoBox } from '@/components/ui/info-box'
import { Toggle } from '@/components/ui/toggle'
import { Reveal } from '@/components/ui/reveal'
import { Badge } from '@/components/ui/badge'
import { SettingsCard, SettingsCardHeader } from '@/components/settings/settings-card'
import { ProfileSection } from '@/components/settings/profile-section'
import { SecuritySection } from '@/components/settings/security-section'
import { NotificationsSection } from '@/components/settings/notifications-section'
import { AppearanceSection } from '@/components/settings/appearance-section'
import { ConnectionsSection, useConnectedCount } from '@/components/settings/connections-section'
import { DangerSection } from '@/components/settings/danger-section'
import { useToast } from '@/hooks/use-toast'
import { useOrgSettings } from '@/hooks/use-org-settings'
import { cn } from '@/lib/utils'
import { ADMIN_LANDING_PATHS } from '@/lib/auth-cookies'

const PREFS_KEY = 'oneai:admin-prefs'
const SUPPORT_EMAIL = 'support@oneai.dev'

const LANDING_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  organizations: 'Organizations',
  agents: 'Agents',
  playground: 'Playground',
  tracing: 'Observability',
}
const ADMIN_LANDING_OPTIONS = ADMIN_LANDING_PATHS.map(p => ({ value: p, label: LANDING_LABELS[p] }))

const SECTIONS = [
  { key: 'profile', label: 'Profile', icon: User },
  { key: 'security', label: 'Security', icon: ShieldCheck },
  { key: 'notifications', label: 'Notifications', icon: Bell },
  { key: 'connections', label: 'Connected Accounts', icon: Plug },
  { key: 'system', label: 'System', icon: Settings2 },
  { key: 'danger', label: 'Danger Zone', icon: AlertTriangle },
] as const

type SectionKey = (typeof SECTIONS)[number]['key']

function SystemSection() {
  const { toast } = useToast()
  const { data, loading, saving, error, save } = useOrgSettings()

  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const [require2fa, setRequire2fa] = useState(false)
  const [sessionTimeout, setSessionTimeout] = useState(true)
  const [sessionDuration, setSessionDuration] = useState('30m')
  const [auditLogging, setAuditLogging] = useState(true)
  const [defaultModel, setDefaultModel] = useState('gpt-4o')

  // Hydrate the form once settings load from the backend.
  useEffect(() => {
    if (!data) return
    setMaintenanceMode(data.maintenance_mode)
    setRequire2fa(data.require_2fa)
    setSessionTimeout(data.session_timeout_enabled)
    setSessionDuration(data.session_duration)
    setAuditLogging(data.audit_logging)
    setDefaultModel(data.default_model)
  }, [data])

  const handleSave = async () => {
    try {
      await save({
        maintenance_mode: maintenanceMode,
        require_2fa: require2fa,
        session_timeout_enabled: sessionTimeout,
        session_duration: sessionDuration,
        audit_logging: auditLogging,
        default_model: defaultModel,
      })
      toast.success('Settings saved successfully')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save settings')
    }
  }

  return (
    <div className="space-y-5">
      {error && <InfoBox variant="warning">{error}</InfoBox>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <SettingsCard>
          <SettingsCardHeader icon={Settings2} title="General" description="Organization-wide behavior" />
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[13px]">Maintenance Mode</span>
              <Toggle checked={maintenanceMode} onChange={setMaintenanceMode} aria-label="Maintenance Mode" />
            </div>
            {maintenanceMode && (
              <InfoBox variant="warning">
                All users see maintenance page when maintenance mode is enabled.
              </InfoBox>
            )}
            <Separator />
            <div>
              <label className="text-[13px] font-medium block mb-2">Default LLM Model</label>
              <Select
                value={defaultModel}
                onValueChange={setDefaultModel}
                options={[
                  { value: 'gpt-4o', label: 'GPT-4o' },
                  { value: 'claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
                  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
                  { value: 'gpt-4o-mini', label: 'GPT-4o-mini' },
                ]}
              />
            </div>
          </div>
        </SettingsCard>

        <SettingsCard>
          <SettingsCardHeader icon={ShieldCheck} title="Org Security" description="Policies applied to every member" />
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[13px]">Require 2FA</span>
              <Toggle checked={require2fa} onChange={setRequire2fa} aria-label="Require 2FA" />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[13px]">Session Timeout</span>
              <Toggle checked={sessionTimeout} onChange={setSessionTimeout} aria-label="Session Timeout" />
            </div>
            {sessionTimeout && (
              <div>
                <label className="text-[13px] font-medium block mb-2">Session Duration</label>
                <Select
                  value={sessionDuration}
                  onValueChange={setSessionDuration}
                  options={[
                    { value: '15m', label: '15 minutes' },
                    { value: '30m', label: '30 minutes' },
                    { value: '1h', label: '1 hour' },
                    { value: '4h', label: '4 hours' },
                    { value: '8h', label: '8 hours' },
                  ]}
                />
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-[13px]">Audit Logging</span>
              <Toggle checked={auditLogging} onChange={setAuditLogging} aria-label="Audit Logging" />
            </div>
          </div>
        </SettingsCard>

        <div className="lg:col-span-2 flex justify-end">
          <Button variant="primary" onClick={handleSave} disabled={loading || saving}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function AdminSettingsPage() {
  const [section, setSection] = useState<SectionKey>('profile')
  const connectedCount = useConnectedCount()

  return (
    <>
      <Reveal>
        <PageHeader title="Settings" description="Your account and organization-wide configuration" />
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
              <ProfileSection requestEmail={SUPPORT_EMAIL} />
            </Reveal>
          )}
          {section === 'security' && (
            <Reveal delay={80}>
              <SecuritySection />
            </Reveal>
          )}
          {section === 'notifications' && (
            <Reveal delay={80} className="space-y-5">
              <AppearanceSection landingOptions={ADMIN_LANDING_OPTIONS} />
              <NotificationsSection storageKey={PREFS_KEY} />
            </Reveal>
          )}
          {section === 'connections' && (
            <Reveal delay={80}>
              <ConnectionsSection manageHref="/admin/connectors" />
            </Reveal>
          )}
          {section === 'system' && (
            <Reveal delay={80}>
              <SystemSection />
            </Reveal>
          )}
          {section === 'danger' && (
            <Reveal delay={80}>
              <DangerSection requestEmail={SUPPORT_EMAIL} />
            </Reveal>
          )}
        </div>
      </div>
    </>
  )
}
