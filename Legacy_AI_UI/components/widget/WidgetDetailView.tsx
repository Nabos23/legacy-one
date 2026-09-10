'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Bot, CheckCircle2, ExternalLink, Eye, History, Key, Loader2, Redo2, RotateCcw, Save, Trash2, Undo2, Upload, Users, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Dialog } from '@/components/ui/dialog'
import { PageHeader } from '@/components/ui/page-header'
import { InfoBox } from '@/components/ui/info-box'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { Tabs } from '@/components/ui/tabs'
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
import { WidgetOverviewTab } from '@/components/widget/WidgetOverviewTab'
import { WidgetEmbedCode } from '@/components/widget/WidgetEmbedCode'
import { WidgetLivePreview } from '@/components/widget/WidgetLivePreview'
import { agentsApi } from '@/lib/api/agents'
import { widgetsApi } from '@/lib/api/widgets'
import { DEFAULT_WIDGET_BRANDING, DEFAULT_WIDGET_LAYOUT } from '@/lib/widget-styles'
import { useToast } from '@/hooks/use-toast'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import type { AgentPublic, WidgetBranding, WidgetBrandingInput, WidgetConfigPublic, WidgetLayout, WidgetSourceType, WidgetVersionListItem } from '@/types'

interface WidgetDetailViewProps {
  basePath: string
}

const TABS = [
  { value: 'overview', label: 'Overview' },
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
  { value: 'embed', label: 'Embed Code' },
  { value: 'history', label: 'History' },
]

const NO_PREVIEW_TABS = new Set(['overview', 'security', 'webhooks', 'embed', 'history'])

function formatVersionTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function toAdvancedValue(widget: WidgetConfigPublic): WidgetAdvancedValue {
  return {
    triggers: widget.triggers,
    behavior: widget.behavior,
    availability: widget.availability,
    accessibility: widget.accessibility,
    layout: widget.layout,
    leadFields: widget.lead_fields,
    webhooks: {
      conversation_started: { url: widget.webhooks.conversation_started.url, is_active: widget.webhooks.conversation_started.is_active },
      lead_captured: { url: widget.webhooks.lead_captured.url, is_active: widget.webhooks.lead_captured.is_active },
      message_sent: { url: widget.webhooks.message_sent?.url, is_active: widget.webhooks.message_sent?.is_active ?? true },
      feedback_submitted: { url: widget.webhooks.feedback_submitted?.url, is_active: widget.webhooks.feedback_submitted?.is_active ?? true },
    },
  }
}

function toBrandingDraft(widget: WidgetConfigPublic): WidgetBrandingInput {
  return { ...widget.branding }
}

export function WidgetDetailView({ basePath }: WidgetDetailViewProps) {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()

  const [activeTab, setActiveTab] = useState('overview')
  const [widget, setWidget] = useState<WidgetConfigPublic | null>(null)
  useBreadcrumbLabel(params.id, widget?.name)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [originInput, setOriginInput] = useState('')
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [regenerateDialogOpen, setRegenerateDialogOpen] = useState(false)

  const [branding, setBranding] = useState<WidgetBrandingInput | null>(null)

  const [advanced, setAdvanced] = useState<WidgetAdvancedValue | null>(null)

  // Undo/redo over the design draft (branding + advanced sections). Rapid
  // edits within 600ms collapse into one history entry so per-keystroke
  // changes undo as a group. Cap 50 entries.
  type DesignSnapshot = { branding: WidgetBrandingInput; advanced: WidgetAdvancedValue }
  const historyRef = useRef<{ past: DesignSnapshot[]; future: DesignSnapshot[]; lastPushAt: number }>({ past: [], future: [], lastPushAt: 0 })
  const [historySizes, setHistorySizes] = useState({ past: 0, future: 0 })
  const brandingRef = useRef<WidgetBrandingInput | null>(null)
  const advancedRef = useRef<WidgetAdvancedValue | null>(null)
  brandingRef.current = branding
  advancedRef.current = advanced

  const syncHistorySizes = () => setHistorySizes({ past: historyRef.current.past.length, future: historyRef.current.future.length })

  const recordHistory = () => {
    if (!brandingRef.current || !advancedRef.current) return
    const h = historyRef.current
    const now = Date.now()
    h.future = []
    if (now - h.lastPushAt > 600) {
      h.past.push({ branding: brandingRef.current, advanced: advancedRef.current })
      if (h.past.length > 50) h.past.shift()
    }
    h.lastPushAt = now
    syncHistorySizes()
  }

  const updateBranding = (next: WidgetBrandingInput) => { recordHistory(); setBranding(next) }
  const updateAdvanced = (next: WidgetAdvancedValue) => { recordHistory(); setAdvanced(next) }

  const resetHistory = () => {
    historyRef.current = { past: [], future: [], lastPushAt: 0 }
    syncHistorySizes()
  }

  const undo = () => {
    const h = historyRef.current
    const snapshot = h.past.pop()
    if (!snapshot || !brandingRef.current || !advancedRef.current) return
    h.future.push({ branding: brandingRef.current, advanced: advancedRef.current })
    h.lastPushAt = 0
    setBranding(snapshot.branding)
    setAdvanced(snapshot.advanced)
    syncHistorySizes()
  }

  const redo = () => {
    const h = historyRef.current
    const snapshot = h.future.pop()
    if (!snapshot || !brandingRef.current || !advancedRef.current) return
    h.past.push({ branding: brandingRef.current, advanced: advancedRef.current })
    h.lastPushAt = 0
    setBranding(snapshot.branding)
    setAdvanced(snapshot.advanced)
    syncHistorySizes()
  }

  // Mod+Z / Mod+Shift+Z (or Ctrl+Y) outside text fields -- inside an input,
  // the browser's native text undo must win.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const target = e.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable) return
      if (e.key.toLowerCase() === 'z') {
        e.preventDefault()
        if (e.shiftKey) redo(); else undo()
      } else if (e.key.toLowerCase() === 'y') {
        e.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [agents, setAgents] = useState<AgentPublic[]>([])
  const [sourceType, setSourceType] = useState<WidgetSourceType>('single_agent')
  const [agentId, setAgentId] = useState('')
  const [nameDraft, setNameDraft] = useState('')
  const [openingPreview, setOpeningPreview] = useState(false)
  const [mobilePreviewOpen, setMobilePreviewOpen] = useState(false)

  const [rateLimitPerMinute, setRateLimitPerMinute] = useState('')
  const [savingRateLimit, setSavingRateLimit] = useState(false)
  const [retentionDays, setRetentionDays] = useState('')
  const [savingRetention, setSavingRetention] = useState(false)

  const [publishing, setPublishing] = useState(false)
  const [discarding, setDiscarding] = useState(false)
  const [versions, setVersions] = useState<WidgetVersionListItem[] | null>(null)
  const [versionsLoading, setVersionsLoading] = useState(false)
  const [rollbackTarget, setRollbackTarget] = useState<WidgetVersionListItem | null>(null)
  const [rollingBack, setRollingBack] = useState(false)

  const load = async () => {
    try {
      const data = await widgetsApi.get(params.id)
      setWidget(data)
      setBranding(toBrandingDraft(data))
      setAdvanced(toAdvancedValue(data))
      resetHistory()
      setSourceType(data.source_type)
      setAgentId(data.agent_id ?? '')
      setNameDraft(data.name)
      setRateLimitPerMinute(data.security.rate_limit_per_minute != null ? String(data.security.rate_limit_per_minute) : '')
      setRetentionDays(data.security.retention_days != null ? String(data.security.retention_days) : '')
      const agentsRes = await agentsApi.listByOrg(data.organization_id, 1, 100, undefined, { isActive: true })
      setAgents(agentsRes.items)
    } catch {
      toast.error('Widget not found')
      router.push(basePath)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [params.id])

  const handleToggleEnabled = async () => {
    if (!widget) return
    const next = !widget.is_enabled
    setWidget({ ...widget, is_enabled: next })
    try {
      await widgetsApi.toggleStatus(widget.id!, next)
      toast.success(next ? 'Widget enabled' : 'Widget disabled')
    } catch {
      setWidget(widget)
      toast.error('Failed to update widget status')
    }
  }

  const addOrigin = async () => {
    if (!widget) return
    const value = originInput.trim()
    if (!value) return
    if (!/^https?:\/\/[^\s]+$/i.test(value)) {
      toast.error('Origins must be a full URL, e.g. https://example.com')
      return
    }
    const normalized = value.replace(/\/$/, '')
    if (widget.security.allowed_origins.includes(normalized)) {
      setOriginInput('')
      return
    }
    const nextOrigins = [...widget.security.allowed_origins, normalized]
    setSaving(true)
    try {
      const updated = await widgetsApi.update(widget.id!, { security: { allowed_origins: nextOrigins } })
      setWidget(updated)
      setOriginInput('')
    } catch {
      toast.error('Failed to add origin')
    } finally {
      setSaving(false)
    }
  }

  const removeOrigin = async (origin: string) => {
    if (!widget) return
    const nextOrigins = widget.security.allowed_origins.filter(o => o !== origin)
    setSaving(true)
    try {
      const updated = await widgetsApi.update(widget.id!, { security: { allowed_origins: nextOrigins } })
      setWidget(updated)
    } catch {
      toast.error('Failed to remove origin')
    } finally {
      setSaving(false)
    }
  }

  const handleRegenerateKey = async () => {
    if (!widget) return
    setRegenerateDialogOpen(false)
    try {
      const res = await widgetsApi.regenerateKey(widget.id!)
      setNewApiKey(res.api_key)
      setWidget({ ...widget, security: { ...widget.security, has_api_key: true } })
      toast.success('New API key generated')
    } catch {
      toast.error('Failed to generate API key')
    }
  }

  const handleDelete = async () => {
    if (!widget) return
    setDeleting(true)
    try {
      await widgetsApi.delete(widget.id!)
      toast.success('Widget deleted')
      router.push(basePath)
    } catch {
      toast.error('Failed to delete widget')
      setDeleting(false)
    }
  }

  // One save for the whole design draft. Every editable section rides in a
  // single PUT -- no more per-tab Save buttons and "did I save that tab?"
  // doubt. Security-tab settings (origins/rate limit/retention/API key) stay
  // separate: they take effect immediately and aren't part of the draft.
  const [savingAll, setSavingAll] = useState(false)
  const handleSaveAll = async () => {
    if (!widget || !branding || !advanced) return
    if (sourceType === 'single_agent' && !agentId) {
      toast.error('Select an agent first (General tab)')
      setActiveTab('general')
      return
    }
    const trimmedName = nameDraft.trim()
    if (trimmedName.length < 2 || trimmedName.length > 120) {
      toast.error('Widget name must be between 2 and 120 characters')
      setActiveTab('general')
      return
    }
    setSavingAll(true)
    try {
      const updated = await widgetsApi.update(widget.id!, {
        name: trimmedName,
        source_type: sourceType,
        agent_id: sourceType === 'single_agent' ? agentId : null,
        branding,
        triggers: advanced.triggers,
        behavior: advanced.behavior,
        availability: advanced.availability,
        accessibility: advanced.accessibility,
        layout: advanced.layout,
        lead_fields: advanced.leadFields,
        webhooks: advanced.webhooks,
      })
      setWidget(updated)
      setBranding(toBrandingDraft(updated))
      setAdvanced(toAdvancedValue(updated))
      setSourceType(updated.source_type)
      setAgentId(updated.agent_id ?? '')
      setNameDraft(updated.name)
      toast.success('Draft saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save changes')
    } finally {
      setSavingAll(false)
    }
  }

  const handlePreviewDraft = async () => {
    if (!widget) return
    setOpeningPreview(true)
    try {
      const res = await widgetsApi.createPreviewToken(widget.id!)
      window.open(`/widget-preview/${widget.id}?preview_token=${encodeURIComponent(res.preview_token)}`, '_blank', 'noopener')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to open draft preview')
    } finally {
      setOpeningPreview(false)
    }
  }

  const handleSaveRateLimit = async () => {
    if (!widget) return
    setSavingRateLimit(true)
    try {
      const updated = await widgetsApi.update(widget.id!, {
        security: {
          allowed_origins: widget.security.allowed_origins,
          // null (not undefined): JSON drops undefined keys entirely, and the
          // backend treats an absent field as "keep" -- null is what clears it.
          rate_limit_per_minute: rateLimitPerMinute.trim() ? Number(rateLimitPerMinute) : null,
        },
      })
      setWidget(updated)
      toast.success('Rate limit saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save rate limit')
    } finally {
      setSavingRateLimit(false)
    }
  }

  const handleSaveRetention = async () => {
    if (!widget) return
    setSavingRetention(true)
    try {
      const updated = await widgetsApi.update(widget.id!, {
        security: {
          allowed_origins: widget.security.allowed_origins,
          retention_days: retentionDays.trim() ? Number(retentionDays) : null,
        },
      })
      setWidget(updated)
      toast.success('Retention policy saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save retention policy')
    } finally {
      setSavingRetention(false)
    }
  }

  const handlePublish = async () => {
    if (!widget) return
    setPublishing(true)
    try {
      const updated = await widgetsApi.publish(widget.id!)
      setWidget(updated)
      toast.success(`Published as v${updated.published_version}`)
      if (activeTab === 'history') void loadVersions()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to publish')
    } finally {
      setPublishing(false)
    }
  }

  const handleDiscardDraft = async () => {
    if (!widget) return
    setDiscarding(true)
    try {
      const updated = await widgetsApi.discardDraft(widget.id!)
      setWidget(updated)
      setBranding(toBrandingDraft(updated))
      setAdvanced(toAdvancedValue(updated))
      resetHistory()
      toast.success('Draft changes discarded')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to discard draft')
    } finally {
      setDiscarding(false)
    }
  }

  const loadVersions = async () => {
    if (!widget) return
    setVersionsLoading(true)
    try {
      const res = await widgetsApi.getVersions(widget.id!, 1, 50)
      setVersions(res.items)
    } catch {
      toast.error('Failed to load publish history')
    } finally {
      setVersionsLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'history' && widget && versions === null) void loadVersions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, widget])

  const handleRollback = async () => {
    if (!widget || !rollbackTarget) return
    setRollingBack(true)
    try {
      const updated = await widgetsApi.rollback(widget.id!, rollbackTarget.version)
      setWidget(updated)
      setBranding(toBrandingDraft(updated))
      setAdvanced(toAdvancedValue(updated))
      resetHistory()
      toast.success(`Restored v${rollbackTarget.version} as v${updated.published_version}`)
      setRollbackTarget(null)
      void loadVersions()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to restore this version')
    } finally {
      setRollingBack(false)
    }
  }

  // Per-tab unsaved-edit tracking: compares the in-memory drafts against the
  // last-loaded widget. Powers the tab dots, the beforeunload guard, and the
  // back-link confirm. (Position lives on branding but is edited in the
  // Launcher tab, so both tabs flag when it changes -- harmless overlap.)
  const dirtyTabs = new Set<string>()
  if (widget && branding && advanced) {
    const savedBranding = toBrandingDraft(widget)
    const savedAdvanced = toAdvancedValue(widget)
    if (JSON.stringify(branding) !== JSON.stringify(savedBranding)) dirtyTabs.add('appearance')
    if (
      JSON.stringify(advanced.layout) !== JSON.stringify(savedAdvanced.layout) ||
      branding.position !== savedBranding.position
    ) {
      dirtyTabs.add('launcher')
      if (JSON.stringify(advanced.layout) !== JSON.stringify(savedAdvanced.layout)) dirtyTabs.add('layout')
    }
    if (JSON.stringify(advanced.triggers) !== JSON.stringify(savedAdvanced.triggers)) dirtyTabs.add('triggers')
    if (JSON.stringify(advanced.behavior) !== JSON.stringify(savedAdvanced.behavior)) dirtyTabs.add('behavior')
    if (JSON.stringify(advanced.availability) !== JSON.stringify(savedAdvanced.availability)) dirtyTabs.add('availability')
    if (JSON.stringify(advanced.accessibility) !== JSON.stringify(savedAdvanced.accessibility)) dirtyTabs.add('accessibility')
    if (JSON.stringify(advanced.leadFields) !== JSON.stringify(savedAdvanced.leadFields)) dirtyTabs.add('leads')
    if (JSON.stringify(advanced.webhooks) !== JSON.stringify(savedAdvanced.webhooks)) dirtyTabs.add('webhooks')
    if (nameDraft !== widget.name || sourceType !== widget.source_type || (sourceType === 'single_agent' && agentId !== (widget.agent_id ?? ''))) {
      dirtyTabs.add('general')
    }
  }
  const hasUnsavedEdits = dirtyTabs.size > 0

  useEffect(() => {
    if (!hasUnsavedEdits) return
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [hasUnsavedEdits])

  if (loading || !widget || !branding || !advanced) {
    return (
      <div className="animate-pulse space-y-5">
        <div className="h-8 w-64 rounded-lg bg-[var(--surface-2)]" />
        <div className="h-12 rounded-[var(--radius-lg)] bg-[var(--surface-2)] border border-[var(--border)]" />
        <div className="flex gap-2 overflow-hidden">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-8 w-24 shrink-0 rounded-lg bg-[var(--surface-2)]" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
          <div className="space-y-4">
            <div className="h-48 rounded-[var(--radius-lg)] bg-[var(--surface-2)] border border-[var(--border)]" />
            <div className="h-32 rounded-[var(--radius-lg)] bg-[var(--surface-2)] border border-[var(--border)]" />
          </div>
          <div className="hidden lg:block h-[560px] rounded-[var(--radius-lg)] bg-[var(--surface-2)] border border-[var(--border)]" />
        </div>
      </div>
    )
  }

  const tabsWithDirtyDots = TABS.map(t => (dirtyTabs.has(t.value) ? { ...t, label: `${t.label} •` } : t))
  const advancedSectionProps = { value: advanced, onChange: updateAdvanced, widgetId: widget.id }

  return (
    <>
      <PageHeader
        title={widget.name}
        description="Manage this widget's appearance, behavior, security, and access"
        actions={
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="xs" onClick={() => setDeleteDialogOpen(true)} title="Delete widget">
              <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
            </Button>
            <Link
              href={basePath}
              onClick={e => {
                if (hasUnsavedEdits && !window.confirm('You have unsaved changes. Leave without saving?')) e.preventDefault()
              }}
            >
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Chatbot Widgets
              </Button>
            </Link>
          </div>
        }
      />

      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <StatusIndicator status={widget.is_enabled ? 'active' : 'inactive'} pulse={widget.is_enabled} />
          <span className="text-[13px] text-[var(--text-2)]">{widget.is_enabled ? 'Enabled' : 'Disabled'}</span>
          <span className="text-[var(--text-3)]">·</span>
          <span className="text-[13px] text-[var(--text-2)] flex items-center gap-1.5">
            {widget.source_type === 'supervisor' ? <Users className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
            {widget.source_type === 'supervisor' ? 'Multi-agent (supervisor)' : 'Single agent'}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={handleToggleEnabled}>
          {widget.is_enabled ? 'Disable' : 'Enable'}
        </Button>
      </div>

      <div className="flex items-center justify-between gap-3 mb-5 px-4 py-3 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-2)]">
        <div className="flex items-center gap-2 text-[13px]">
          {widget.has_unpublished_changes ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
              <span className="text-[var(--text-1)] font-medium">Unpublished changes</span>
              <span className="text-[var(--text-3)]">
                — visitors still see v{widget.published_version ?? '—'}
                {widget.published_at ? ` (published ${formatVersionTime(widget.published_at)})` : ''}
              </span>
            </>
          ) : widget.published_version ? (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span className="text-[var(--text-2)]">
                Published as v{widget.published_version}
                {widget.published_at ? ` · ${formatVersionTime(widget.published_at)}` : ''}
              </span>
            </>
          ) : (
            <span className="text-[var(--text-3)]">Not published yet</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center rounded-lg border border-[var(--border)] p-0.5 mr-1">
            <Button variant="ghost" size="xs" onClick={undo} disabled={historySizes.past === 0} title="Undo (Ctrl+Z)">
              <Undo2 className="w-3.5 h-3.5" />
            </Button>
            <Button variant="ghost" size="xs" onClick={redo} disabled={historySizes.future === 0} title="Redo (Ctrl+Shift+Z)">
              <Redo2 className="w-3.5 h-3.5" />
            </Button>
          </div>
          <Button variant="ghost" size="sm" onClick={handlePreviewDraft} disabled={openingPreview} title="Open the draft in the test page (15-minute preview link)">
            {openingPreview ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ExternalLink className="w-3.5 h-3.5 mr-1.5" />}
            Preview draft
          </Button>
          {widget.has_unpublished_changes && (
            <>
              <Button variant="ghost" size="sm" onClick={handleDiscardDraft} disabled={discarding || publishing}>
                {discarding ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Undo2 className="w-3.5 h-3.5 mr-1.5" />}
                Discard changes
              </Button>
              <Button variant="primary" size="sm" onClick={handlePublish} disabled={publishing || discarding}>
                {publishing ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
                Publish
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="mb-6 overflow-x-auto">
        <Tabs tabs={tabsWithDirtyDots} value={activeTab} onChange={setActiveTab} className="min-w-max" />
      </div>

      <div className={!NO_PREVIEW_TABS.has(activeTab) ? 'grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start' : ''}>
      <div className={`space-y-6 min-w-0 ${activeTab === 'overview' ? '' : 'max-w-3xl'}`}>
        {activeTab === 'overview' && <WidgetOverviewTab widgetId={widget.id!} />}

        {activeTab === 'general' && (
          <>
            <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
              <div>
                <label className="text-[13px] font-medium block mb-2">Widget name</label>
                <Input value={nameDraft} onChange={e => setNameDraft(e.target.value)} maxLength={120} />
              </div>
              <p className="text-[14px] font-semibold text-[var(--text-1)]">Agent source</p>
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
                    Visitors chat with exactly one agent you pick below.
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
                    Auto-routes across every active agent in this org, same as the Playground&apos;s Supervisor mode.
                  </p>
                </button>
              </div>

              {sourceType === 'single_agent' ? (
                <div>
                  <label className="text-[13px] font-medium block mb-2">Agent</label>
                  <Select
                    value={agentId}
                    onValueChange={setAgentId}
                    options={agents.map(a => ({ value: a.id!, label: a.name }))}
                    placeholder={agents.length === 0 ? 'No active agents in this organization' : 'Select an agent'}
                    disabled={agents.length === 0}
                  />
                </div>
              ) : (
                <InfoBox variant="warning">
                  This exposes every active agent in this organization ({agents.length}) to anonymous website
                  visitors via delegation. Make sure none of those agents carry tools or data you don&apos;t want
                  reachable from a public embed.
                </InfoBox>
              )}

            </div>

            <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-2">
              <p className="text-[13px] text-[var(--text-2)]">
                <span className="font-medium">Created:</span> {new Date(widget.created_at).toLocaleString()}
              </p>
              <p className="text-[13px] text-[var(--text-2)]">
                <span className="font-medium">Last updated:</span> {new Date(widget.updated_at).toLocaleString()}
              </p>
            </div>
          </>
        )}

        {activeTab === 'appearance' && (
          <>
            <WidgetAppearanceSection branding={branding} onChange={updateBranding} widgetId={widget.id!} />
            <Button
              variant="ghost"
              onClick={() => updateBranding({ ...DEFAULT_WIDGET_BRANDING })}
              title="Reset appearance fields to their defaults (undoable; not saved until you save the draft)"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset to default
            </Button>
          </>
        )}

        {activeTab === 'launcher' && (
          <>
            <LauncherSection
              {...advancedSectionProps}
              position={branding.position}
              onPositionChange={position => updateBranding({ ...branding, position })}
            />
          </>
        )}

        {activeTab === 'layout' && (
          <>
            <LayoutSection {...advancedSectionProps} />
            <Button
              variant="ghost"
              className="mt-4"
              onClick={() => updateAdvanced({ ...advanced, layout: { ...DEFAULT_WIDGET_LAYOUT } })}
              title="Reset layout fields to their defaults (undoable; not saved until you save the draft)"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset to default
            </Button>
          </>
        )}
        {activeTab === 'triggers' && <TriggersSection {...advancedSectionProps} />}
        {activeTab === 'behavior' && <BehaviorSection {...advancedSectionProps} />}
        {activeTab === 'availability' && <AvailabilitySection {...advancedSectionProps} />}
        {activeTab === 'accessibility' && <AccessibilitySection {...advancedSectionProps} />}
        {activeTab === 'leads' && <LeadCaptureSection {...advancedSectionProps} />}
        {activeTab === 'webhooks' && <WebhooksSection {...advancedSectionProps} />}

        {activeTab === 'security' && (
          <>
            <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
              <p className="text-[14px] font-semibold text-[var(--text-1)]">Allowed origins</p>
              <p className="text-[12px] text-[var(--text-3)]">
                Only websites on this list can load the embedded widget.
              </p>
              <div className="flex gap-2">
                <Input
                  value={originInput}
                  onChange={e => setOriginInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addOrigin() } }}
                  placeholder="https://your-customer-site.com"
                  disabled={saving}
                />
                <Button variant="outline" onClick={addOrigin} disabled={saving}>Add</Button>
              </div>
              {widget.security.allowed_origins.length === 0 ? (
                <p className="text-[12px] text-[var(--text-3)]">No origins allowed yet — the widget can&apos;t be embedded anywhere until you add one.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {widget.security.allowed_origins.map(origin => (
                    <span key={origin} className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300 rounded-full px-2.5 py-1 text-[12px]">
                      {origin}
                      <button type="button" onClick={() => removeOrigin(origin)} disabled={saving}>
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
              <p className="text-[14px] font-semibold text-[var(--text-1)]">Rate limit</p>
              <p className="text-[12px] text-[var(--text-3)]">
                Optional cap specific to this widget, on top of the platform-wide limit. Leave blank for no extra cap.
              </p>
              <div className="flex gap-2 items-center">
                <Input
                  type="number"
                  min={1}
                  value={rateLimitPerMinute}
                  onChange={e => setRateLimitPerMinute(e.target.value)}
                  placeholder="No widget-specific limit"
                  className="max-w-[220px]"
                />
                <span className="text-[12px] text-[var(--text-3)]">requests/minute</span>
                <Button variant="outline" size="sm" onClick={handleSaveRateLimit} disabled={savingRateLimit} className="ml-auto">
                  {savingRateLimit ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
                  Save
                </Button>
              </div>
            </div>

            <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
              <p className="text-[14px] font-semibold text-[var(--text-1)]">Data retention</p>
              <p className="text-[12px] text-[var(--text-3)]">
                Automatically delete visitor sessions, captured leads, and message feedback after this many
                days. Applies to conversations started after saving; leave blank to keep data indefinitely.
              </p>
              <div className="flex gap-2 items-center">
                <Input
                  type="number"
                  min={1}
                  max={3650}
                  value={retentionDays}
                  onChange={e => setRetentionDays(e.target.value)}
                  placeholder="Keep forever"
                  className="max-w-[220px]"
                />
                <span className="text-[12px] text-[var(--text-3)]">days</span>
                <Button variant="outline" size="sm" onClick={handleSaveRetention} disabled={savingRetention} className="ml-auto">
                  {savingRetention ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
                  Save
                </Button>
              </div>
            </div>

            <div className="card-1 p-6 rounded-[var(--radius-lg)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[14px] font-semibold text-[var(--text-1)]">Widget API key</p>
                  <p className="text-[12px] text-[var(--text-3)] mt-1">
                    {widget.security.has_api_key ? 'A key is set' : 'No key generated yet'} — optional secondary
                    factor alongside the origin allowlist.
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => setRegenerateDialogOpen(true)}>
                  <Key className="w-3.5 h-3.5 mr-2" />
                  {widget.security.has_api_key ? 'Regenerate' : 'Generate'}
                </Button>
              </div>
              {newApiKey && (
                <InfoBox variant="success">
                  <span className="font-mono break-all">{newApiKey}</span>
                  <p className="mt-2 text-[11px]">Copy this now — it won&apos;t be shown again.</p>
                </InfoBox>
              )}
            </div>
          </>
        )}

        {activeTab === 'embed' && (
          <div className="card-1 p-6 rounded-[var(--radius-lg)]">
            <WidgetEmbedCode widgetId={widget.id!} />
          </div>
        )}

        {activeTab === 'history' && (
          <div className="card-1 p-6 rounded-[var(--radius-lg)]">
            <p className="text-[14px] font-semibold text-[var(--text-1)] mb-1">Publish history</p>
            <p className="text-[12px] text-[var(--text-3)] mb-4">
              Every time you publish (or restore a past version), a new entry is recorded here. Restoring an
              older version publishes its content again as the newest version — history never branches.
            </p>
            {versionsLoading ? (
              <div className="h-24 rounded-xl bg-[var(--surface-2)] animate-pulse" />
            ) : !versions || versions.length === 0 ? (
              <p className="text-[13px] text-[var(--text-3)]">No published versions yet.</p>
            ) : (
              <div className="space-y-2">
                {versions.map(v => {
                  const isCurrent = v.version === widget.published_version
                  return (
                    <div
                      key={v.version}
                      className={`flex items-center justify-between gap-3 px-4 py-3 rounded-[var(--radius-md)] border ${
                        isCurrent ? 'border-violet-400 bg-violet-500/5' : 'border-[var(--border)]'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <History className="w-3.5 h-3.5 text-[var(--text-3)] shrink-0" />
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium">
                            v{v.version}
                            {isCurrent && <span className="ml-2 text-[11px] text-violet-600 dark:text-violet-400">Current</span>}
                            {v.restored_from_version != null && (
                              <span className="ml-2 text-[11px] text-[var(--text-3)]">restored from v{v.restored_from_version}</span>
                            )}
                          </p>
                          <p className="text-[11.5px] text-[var(--text-3)]">
                            {formatVersionTime(v.published_at)}
                            {v.published_by_name ? ` · by ${v.published_by_name}` : ''}
                            {(v.changed_sections?.length ?? 0) > 0 && (
                              <> · changed: {v.changed_sections!.map(sec => sec.replace('_', ' ')).join(', ')}</>
                            )}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => setRollbackTarget(v)}
                        disabled={isCurrent}
                      >
                        Restore
                      </Button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
      {!NO_PREVIEW_TABS.has(activeTab) && (
        <div className="hidden lg:block">
          <WidgetLivePreview
            branding={{ ...widget.branding, ...branding } as WidgetBranding}
            layout={{ ...widget.layout, ...advanced.layout } as WidgetLayout}
            onNavigate={target => setActiveTab(target)}
          />
        </div>
      )}
      </div>

      {/* Mobile/tablet: the preview column is hidden below lg, so offer it as
          a floating sheet instead of losing it entirely. */}
      {!NO_PREVIEW_TABS.has(activeTab) && (
        <Button
          variant="primary"
          size="sm"
          onClick={() => setMobilePreviewOpen(true)}
          className="lg:hidden fixed bottom-20 right-4 z-30 rounded-full shadow-lg"
        >
          <Eye className="w-4 h-4 mr-1.5" />
          Preview
        </Button>
      )}
      <Dialog open={mobilePreviewOpen} onOpenChange={setMobilePreviewOpen} title="Live preview">
        <WidgetLivePreview
          branding={{ ...widget.branding, ...branding } as WidgetBranding}
          layout={{ ...widget.layout, ...advanced.layout } as WidgetLayout}
        />
      </Dialog>

      {/* 3: the one save bar. Appears whenever any tab has unsaved edits. */}
      {hasUnsavedEdits && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-4 py-2.5 rounded-full border border-[var(--border)] bg-[var(--surface)] shadow-xl">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
          <span className="text-[13px] text-[var(--text-2)]">Unsaved changes</span>
          <Button variant="primary" size="sm" onClick={handleSaveAll} disabled={savingAll} className="rounded-full">
            {savingAll ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
            Save draft
          </Button>
        </div>
      )}

      <Dialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete widget"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleting}>
              {deleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Delete
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Delete <strong>{widget.name}</strong>? Its embed script will stop working immediately. This cannot be undone.
        </p>
      </Dialog>

      <Dialog
        open={regenerateDialogOpen}
        onOpenChange={setRegenerateDialogOpen}
        title={widget.security.has_api_key ? 'Regenerate API key' : 'Generate API key'}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setRegenerateDialogOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleRegenerateKey}>
              {widget.security.has_api_key ? 'Regenerate' : 'Generate'}
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          {widget.security.has_api_key
            ? 'This invalidates the previous key immediately. Any integration still using it will stop authenticating.'
            : 'A new widget API key will be generated and shown once.'}
        </p>
      </Dialog>

      <Dialog
        open={rollbackTarget !== null}
        onOpenChange={open => { if (!open) setRollbackTarget(null) }}
        title={`Restore v${rollbackTarget?.version ?? ''}`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setRollbackTarget(null)}>Cancel</Button>
            <Button variant="primary" onClick={handleRollback} disabled={rollingBack}>
              {rollingBack && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Restore &amp; publish
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          This publishes v{rollbackTarget?.version}&apos;s content again as a new version, visible to visitors
          immediately, and replaces your current draft with it. Any unpublished changes on the draft right now
          will be lost.
        </p>
      </Dialog>
    </>
  )
}
