'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Bot, Check, FileText, Headphones, Loader2, Sparkles, TrendingUp, Users, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { InfoBox } from '@/components/ui/info-box'
import { Tabs } from '@/components/ui/tabs'
import { FormField } from '@/components/ui/form-field'
import {
  AccessibilitySection,
  AvailabilitySection,
  BehaviorSection,
  LauncherSection,
  LayoutSection,
  LeadCaptureSection,
  TriggersSection,
  WebhooksSection,
  type WidgetAdvancedValue,
} from '@/components/widget/WidgetAdvancedSettings'
import { WidgetAppearanceSection } from '@/components/widget/WidgetAppearanceSection'
import { WidgetLivePreview } from '@/components/widget/WidgetLivePreview'
import { useAuth } from '@/contexts/auth-context'
import { useOrganizations } from '@/hooks/use-organizations'
import { useToast } from '@/hooks/use-toast'
import { agentsApi } from '@/lib/api/agents'
import { widgetsApi } from '@/lib/api/widgets'
import { DEFAULT_WIDGET_BRANDING, DEFAULT_WIDGET_LAYOUT } from '@/lib/widget-styles'
import { WIDGET_TEMPLATES, type WidgetTemplate } from '@/lib/widget-templates'
import type { AgentPublic, WidgetBranding, WidgetBrandingInput, WidgetLayout, WidgetPosition, WidgetSourceType } from '@/types'

interface WidgetCreateFormProps {
  basePath: string
  /** Show an organization picker (super admins only) instead of assuming the current user's org. */
  allowOrgSelect?: boolean
}

const TABS = [
  { value: 'general', label: 'General' },
  { value: 'appearance', label: 'Appearance' },
  { value: 'launcher', label: 'Launcher' },
  { value: 'layout', label: 'Layout' },
  { value: 'triggers', label: 'Triggers' },
  { value: 'behavior', label: 'Behavior' },
  { value: 'availability', label: 'Availability' },
  { value: 'accessibility', label: 'Accessibility' },
  { value: 'leads', label: 'Lead Capture' },
  { value: 'webhooks', label: 'Webhooks' },
  { value: 'security', label: 'Security' },
]

const NO_PREVIEW_TABS = new Set(['security', 'webhooks'])

const TEMPLATE_ICONS: Record<string, typeof Sparkles> = {
  blank: Sparkles,
  support: Headphones,
  sales: TrendingUp,
  docs: FileText,
}

const EMPTY_ADVANCED: WidgetAdvancedValue = {
  triggers: { auto_open: false, auto_open_delay_ms: 4000, open_on_scroll_percent: null, targeted_greetings: [] },
  behavior: { response_language: 'auto', tone_instructions: '', welcome_sound: false, allow_attachments: false },
  availability: { enabled: false, timezone: 'UTC', schedule: {}, offline_message: "We're offline right now. Leave a message and we'll get back to you." },
  accessibility: { reduced_motion: false, high_contrast: false, large_text: false },
  layout: DEFAULT_WIDGET_LAYOUT,
  leadFields: [],
  webhooks: {},
}

/** Fills in every required field for the live preview, which expects a full
 * WidgetBranding, not the partial *Input the form edits. */
function toPreviewBranding(branding: WidgetBrandingInput): WidgetBranding {
  return { ...DEFAULT_WIDGET_BRANDING, ...branding } as WidgetBranding
}

function toPreviewLayout(layout: WidgetAdvancedValue['layout']): WidgetLayout {
  return { ...EMPTY_ADVANCED.layout, ...layout } as WidgetLayout
}

export function WidgetCreateForm({ basePath, allowOrgSelect }: WidgetCreateFormProps) {
  const router = useRouter()
  const { user, permissions } = useAuth()
  const { toast } = useToast()
  const isSuperAdmin = !!permissions?.is_super_admin
  const showOrgSelect = !!allowOrgSelect && isSuperAdmin

  const [activeTab, setActiveTab] = useState('general')
  const { data: orgsData } = useOrganizations(1, undefined, 100)
  const orgs = orgsData?.items ?? []
  const [organizationId, setOrganizationId] = useState('')
  const effectiveOrgId = showOrgSelect ? organizationId : (user?.organization_id ?? '')

  const [agents, setAgents] = useState<AgentPublic[]>([])
  const [name, setName] = useState('')
  const [sourceType, setSourceType] = useState<WidgetSourceType>('single_agent')
  const [agentId, setAgentId] = useState('')
  const [templateKey, setTemplateKey] = useState('blank')
  const [branding, setBranding] = useState<WidgetBrandingInput>(DEFAULT_WIDGET_BRANDING)
  const [allowedOrigins, setAllowedOrigins] = useState<string[]>([])
  const [originInput, setOriginInput] = useState('')
  const [rateLimitPerMinute, setRateLimitPerMinute] = useState('')
  const [advanced, setAdvanced] = useState<WidgetAdvancedValue>(EMPTY_ADVANCED)
  const [loading, setLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const clearFieldError = (key: string) =>
    setFieldErrors(prev => {
      if (!(key in prev)) return prev
      const { [key]: _omit, ...rest } = prev
      return rest
    })

  useEffect(() => {
    if (showOrgSelect && orgs.length > 0 && !organizationId) {
      setOrganizationId(orgs[0].id!)
    }
  }, [showOrgSelect, orgs, organizationId])

  useEffect(() => {
    if (!effectiveOrgId) { setAgents([]); return }
    agentsApi.listByOrg(effectiveOrgId, 1, 100, undefined, { isActive: true }).then(d => setAgents(d.items))
    setAgentId('')
  }, [effectiveOrgId])

  /** Re-seed branding/behavior/leads/triggers/availability from the picked
   * template over the blank defaults -- everything stays editable after. */
  const applyTemplate = (tpl: WidgetTemplate) => {
    setTemplateKey(tpl.key)
    setBranding({ ...DEFAULT_WIDGET_BRANDING, ...(tpl.branding ?? {}) })
    setAdvanced({
      ...EMPTY_ADVANCED,
      triggers: { ...EMPTY_ADVANCED.triggers, ...(tpl.triggers ?? {}) },
      behavior: { ...EMPTY_ADVANCED.behavior, ...(tpl.behavior ?? {}) },
      availability: { ...EMPTY_ADVANCED.availability, ...(tpl.availability ?? {}) },
      leadFields: tpl.leadFields ? tpl.leadFields.map(f => ({ ...f })) : [],
    })
  }

  const addOrigin = () => {
    const value = originInput.trim()
    if (!value) return
    if (!/^https?:\/\/[^\s]+$/i.test(value)) {
      setFieldErrors(prev => ({ ...prev, origin: 'Origins must be a full URL, e.g. https://example.com' }))
      return
    }
    const normalized = value.replace(/\/$/, '')
    if (!allowedOrigins.includes(normalized)) {
      setAllowedOrigins(prev => [...prev, normalized])
    }
    setOriginInput('')
    clearFieldError('origin')
  }

  const removeOrigin = (origin: string) => {
    setAllowedOrigins(prev => prev.filter(o => o !== origin))
  }

  const canSubmit =
    name.trim().length >= 2 &&
    !!effectiveOrgId &&
    (sourceType === 'supervisor' || !!agentId) &&
    !loading

  const validate = () => {
    const errors: Record<string, string> = {}
    if (name.trim().length < 2) errors.name = 'Name must be at least 2 characters'
    if (!effectiveOrgId) errors.organization_id = 'Select an organization'
    if (sourceType === 'single_agent' && !agentId) errors.agent_id = 'Select an agent'
    return errors
  }

  const handleCreate = async () => {
    if (!effectiveOrgId) return
    const errors = validate()
    if (Object.keys(errors).length > 0) {
      setFieldErrors(prev => ({ ...prev, ...errors }))
      return
    }
    setLoading(true)
    try {
      const widget = await widgetsApi.create({
        organization_id: effectiveOrgId,
        name: name.trim(),
        source_type: sourceType,
        agent_id: sourceType === 'single_agent' ? agentId : undefined,
        branding,
        layout: advanced.layout,
        triggers: advanced.triggers,
        behavior: advanced.behavior,
        availability: advanced.availability,
        accessibility: advanced.accessibility,
        lead_fields: advanced.leadFields,
        webhooks: advanced.webhooks,
        security: {
          allowed_origins: allowedOrigins,
          rate_limit_per_minute: rateLimitPerMinute.trim() ? Number(rateLimitPerMinute) : undefined,
        },
      })
      toast.success('Widget created')
      if (allowedOrigins.length === 0) {
        toast.warning('No allowed origins yet — the widget can’t be embedded anywhere until you add one on the Security tab.')
      }
      router.push(`${basePath}/${widget.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create widget')
    } finally {
      setLoading(false)
    }
  }

  const advancedSectionProps = { value: advanced, onChange: setAdvanced }

  const originsEditor = (
    <>
      <FormField error={fieldErrors.origin}>
        <div className="flex gap-2">
          <Input
            value={originInput}
            onChange={e => {
              setOriginInput(e.target.value)
              clearFieldError('origin')
            }}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addOrigin() } }}
            placeholder="https://your-customer-site.com"
          />
          <Button variant="outline" onClick={addOrigin}>Add</Button>
        </div>
      </FormField>
      {allowedOrigins.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {allowedOrigins.map(origin => (
            <span key={origin} className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300 rounded-full px-2.5 py-1 text-[12px]">
              {origin}
              <button type="button" onClick={() => removeOrigin(origin)}>
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </>
  )

  return (
    <>
      <PageHeader
        title="New Chatbot Widget"
        description="Configure appearance, behavior, and access for an embeddable chat widget"
        actions={
          <Link href={basePath}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Chatbot Widgets
            </Button>
          </Link>
        }
      />

      <Tabs tabs={TABS} value={activeTab} onChange={setActiveTab} className="mb-6" />

      <div className={!NO_PREVIEW_TABS.has(activeTab) ? 'grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start' : ''}>
      <div className="space-y-6 min-w-0 max-w-3xl">
          {activeTab === 'general' && (
            <>
              <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-3">
                <div>
                  <p className="text-[14px] font-semibold text-[var(--text-1)]">Start from a template</p>
                  <p className="text-[12px] text-[var(--text-3)] mt-0.5">
                    Pre-fills copy, behavior, and lead capture for a common use case — everything stays editable.
                  </p>
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {WIDGET_TEMPLATES.map(tpl => {
                    const Icon = TEMPLATE_ICONS[tpl.key] ?? Sparkles
                    const active = templateKey === tpl.key
                    return (
                      <button
                        key={tpl.key}
                        type="button"
                        onClick={() => applyTemplate(tpl)}
                        className={`text-left p-4 rounded-[var(--radius-lg)] border transition-colors ${
                          active ? 'border-violet-500 bg-violet-500/10' : 'border-[var(--border)] hover:border-violet-300'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <Icon className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                          {active && <Check className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400" />}
                        </div>
                        <p className="text-[13.5px] font-medium">{tpl.label}</p>
                        <p className="text-[11.5px] text-[var(--text-3)] mt-1">{tpl.description}</p>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
              {showOrgSelect && (
                <FormField label="Organization" required error={fieldErrors.organization_id}>
                  <Select
                    value={organizationId}
                    onValueChange={v => {
                      setOrganizationId(v)
                      clearFieldError('organization_id')
                    }}
                    options={orgs.map(org => ({ value: org.id!, label: org.name }))}
                  />
                </FormField>
              )}

              <FormField label="Widget name" required error={fieldErrors.name}>
                <Input
                  value={name}
                  onChange={e => {
                    setName(e.target.value)
                    clearFieldError('name')
                  }}
                  placeholder="Support widget"
                />
              </FormField>

              <FormField label="Agent source">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setSourceType('single_agent')}
                    className={`text-left p-4 rounded-[var(--radius-lg)] border transition-colors ${
                      sourceType === 'single_agent'
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-[var(--border)] hover:border-violet-300'
                    }`}
                  >
                    <Bot className="w-4 h-4 text-violet-600 dark:text-violet-400 mb-2" />
                    <p className="text-[14px] font-medium">Single agent</p>
                    <p className="text-[12px] text-[var(--text-3)] mt-1">
                      Visitors chat with exactly one agent you pick below. Smallest exposure surface.
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSourceType('supervisor')}
                    className={`text-left p-4 rounded-[var(--radius-lg)] border transition-colors ${
                      sourceType === 'supervisor'
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-[var(--border)] hover:border-violet-300'
                    }`}
                  >
                    <Users className="w-4 h-4 text-violet-600 dark:text-violet-400 mb-2" />
                    <p className="text-[14px] font-medium">Multi-agent (Supervisor)</p>
                    <p className="text-[12px] text-[var(--text-3)] mt-1">
                      Same routing as the Playground&apos;s Supervisor mode — auto-routes across every active agent in this org.
                    </p>
                  </button>
                </div>
              </FormField>

              {sourceType === 'single_agent' ? (
                <FormField label="Agent" required error={fieldErrors.agent_id}>
                  <Select
                    value={agentId}
                    onValueChange={v => {
                      setAgentId(v)
                      clearFieldError('agent_id')
                    }}
                    options={agents.map(a => ({ value: a.id!, label: a.name }))}
                    placeholder={agents.length === 0 ? 'No active agents in this organization' : 'Select an agent'}
                    disabled={agents.length === 0}
                  />
                </FormField>
              ) : (
                <InfoBox variant="warning">
                  This exposes every active agent in this organization ({agents.length}) to anonymous website
                  visitors via delegation — the same routing the Playground&apos;s Supervisor mode uses internally,
                  now made public. Make sure none of those agents carry tools or data you don&apos;t want reachable
                  from a public embed.
                </InfoBox>
              )}
              </div>

              <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
                <p className="text-[14px] font-semibold text-[var(--text-1)]">Allowed origins</p>
                <p className="text-[12px] text-[var(--text-3)]">
                  Only websites on this list will be allowed to load the embedded widget — without at least one,
                  it can&apos;t be embedded anywhere. You can add more later on the Security tab.
                </p>
                {originsEditor}
              </div>
            </>
          )}

          {activeTab === 'appearance' && (
            <WidgetAppearanceSection branding={branding} onChange={setBranding} />
          )}

          {activeTab === 'launcher' && (
            <LauncherSection
              {...advancedSectionProps}
              position={branding.position ?? 'bottom-right'}
              onPositionChange={(position: WidgetPosition) => setBranding(prev => ({ ...prev, position }))}
            />
          )}
          {activeTab === 'layout' && <LayoutSection {...advancedSectionProps} />}
          {activeTab === 'triggers' && <TriggersSection {...advancedSectionProps} />}
          {activeTab === 'behavior' && <BehaviorSection {...advancedSectionProps} />}
          {activeTab === 'availability' && <AvailabilitySection {...advancedSectionProps} />}
          {activeTab === 'accessibility' && <AccessibilitySection {...advancedSectionProps} />}
          {activeTab === 'leads' && <LeadCaptureSection {...advancedSectionProps} />}
          {activeTab === 'webhooks' && <WebhooksSection {...advancedSectionProps} />}

          {activeTab === 'security' && (
            <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
              <p className="text-[14px] font-semibold text-[var(--text-1)]">Allowed origins</p>
              <p className="text-[12px] text-[var(--text-3)]">
                Only websites on this list will be allowed to load the embedded widget. You can add more later.
              </p>
              {originsEditor}

              <FormField
                label="Rate limit (requests/minute)"
                hint="Optional cap specific to this widget, on top of the platform-wide limit. Leave blank for no extra cap."
              >
                <Input
                  type="number"
                  min={1}
                  value={rateLimitPerMinute}
                  onChange={e => setRateLimitPerMinute(e.target.value)}
                  placeholder="No widget-specific limit"
                  className="max-w-[220px]"
                />
              </FormField>
            </div>
          )}

          <Button variant="primary" size="lg" className="w-full" onClick={handleCreate} disabled={!canSubmit}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Create Widget
          </Button>
      </div>
      {!NO_PREVIEW_TABS.has(activeTab) && (
        <div className="hidden lg:block">
          <WidgetLivePreview
            branding={toPreviewBranding(branding)}
            layout={toPreviewLayout(advanced.layout)}
            availability={advanced.availability}
          />
        </div>
      )}
      </div>
    </>
  )
}
