'use client'

import { useEffect, useState } from 'react'
import { Bot, ExternalLink, Loader2, MessageCircle, Plug, Trash2, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { connectorAppsApi, agentsApi, SLACK_APP_INSTALL_URL } from '@/lib/api'
import type { SlackAppSourceType, SlackInstallation } from '@/lib/api'
import type { AgentPublic } from '@/types'
import { useToast } from '@/hooks/use-toast'

interface SlackInstallationsViewProps {
  /** The org this page manages installations for. Admin pages resolve this
   * themselves (super-admin org picker); client pages just pass the
   * caller's own organization_id. */
  organizationId: string
}

/** Rebind an installation's agent (mirrors WidgetCreateForm's source-type
 * card + agent Select pattern), or disable/delete it. */
function RebindDialog({
  installation,
  organizationId,
  onClose,
  onSaved,
}: {
  installation: SlackInstallation
  organizationId: string
  onClose: () => void
  onSaved: (updated: SlackInstallation) => void
}) {
  const { toast } = useToast()
  const [sourceType, setSourceType] = useState<SlackAppSourceType>(installation.source_type ?? 'supervisor')
  const [agentId, setAgentId] = useState(installation.agent_id ?? '')
  const [agents, setAgents] = useState<AgentPublic[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    agentsApi.listByOrg(organizationId, 1, 100, undefined, { isActive: true }).then(res => setAgents(res.items))
  }, [organizationId])

  const handleSave = async () => {
    if (sourceType === 'single_agent' && !agentId) {
      toast.error('Select an agent first')
      return
    }
    setSaving(true)
    try {
      const updated = await connectorAppsApi.slack.update(installation.id, {
        source_type: sourceType,
        agent_id: sourceType === 'single_agent' ? agentId : null,
      })
      toast.success('Slack workspace updated')
      onSaved(updated)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open
      onOpenChange={open => !open && onClose()}
      title={`Rebind ${installation.team_name ?? 'Slack workspace'}`}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Save
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <button
          type="button"
          onClick={() => setSourceType('supervisor')}
          className={`text-left p-3 rounded-[var(--radius-lg)] border transition-colors ${
            sourceType === 'supervisor' ? 'border-violet-500 bg-violet-500/10' : 'border-[var(--border)] hover:border-violet-300'
          }`}
        >
          <Users className="w-4 h-4 text-violet-600 dark:text-violet-400 mb-1.5" />
          <p className="text-[13px] font-medium">Multi-agent (Supervisor)</p>
        </button>
        <button
          type="button"
          onClick={() => setSourceType('single_agent')}
          className={`text-left p-3 rounded-[var(--radius-lg)] border transition-colors ${
            sourceType === 'single_agent' ? 'border-violet-500 bg-violet-500/10' : 'border-[var(--border)] hover:border-violet-300'
          }`}
        >
          <Bot className="w-4 h-4 text-violet-600 dark:text-violet-400 mb-1.5" />
          <p className="text-[13px] font-medium">Single agent</p>
        </button>
      </div>
      {sourceType === 'single_agent' && (
        <Select
          value={agentId}
          onValueChange={setAgentId}
          options={agents.map(a => ({ value: a.id!, label: a.name }))}
          placeholder={agents.length === 0 ? 'No active agents' : 'Select an agent'}
          disabled={agents.length === 0}
        />
      )}
    </Dialog>
  )
}

export function SlackInstallationsView({ organizationId }: SlackInstallationsViewProps) {
  const { toast } = useToast()
  const [installations, setInstallations] = useState<SlackInstallation[]>([])
  const [loading, setLoading] = useState(true)
  const [rebindTarget, setRebindTarget] = useState<SlackInstallation | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<SlackInstallation | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = async () => {
    if (!organizationId) return
    setLoading(true)
    try {
      setInstallations(await connectorAppsApi.slack.list(organizationId))
    } catch {
      toast.error('Failed to load Slack installations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [organizationId])

  const handleToggleEnabled = async (installation: SlackInstallation) => {
    try {
      const updated = await connectorAppsApi.slack.update(installation.id, { is_enabled: !installation.is_enabled })
      setInstallations(prev => prev.map(i => (i.id === updated.id ? updated : i)))
    } catch {
      toast.error('Failed to update status')
    }
  }

  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await connectorAppsApi.slack.delete(deleteTarget.id)
      setInstallations(prev => prev.filter(i => i.id !== deleteTarget.id))
      toast.success('Slack workspace disconnected')
      setDeleteTarget(null)
    } catch {
      toast.error('Failed to disconnect')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Slack App"
        description="Chat with a One-AI agent right from Slack — manage which workspaces are connected and which agent answers each one."
        actions={
          <a href={SLACK_APP_INSTALL_URL}>
            <Button className="pl-3 pr-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl shadow-md shadow-violet-500/20">
              <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
              Add to Slack
            </Button>
          </a>
        }
      />

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div key={i} className="h-20 rounded-[var(--radius-lg)] bg-[var(--surface-2)] animate-pulse border border-[var(--border)]" />
          ))}
        </div>
      ) : installations.length === 0 ? (
        <EmptyState
          icon={MessageCircle}
          title="No Slack workspaces connected yet"
          description="Install the One-AI Slack App in your workspace, then finish setup from the DM it sends you."
          action={
            <a href={SLACK_APP_INSTALL_URL}>
              <Button className="pl-3 pr-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl">
                <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                Add to Slack
              </Button>
            </a>
          }
        />
      ) : (
        <div className="space-y-3">
          {installations.map(installation => (
            <div
              key={installation.id}
              className="card-1 rounded-[var(--radius-lg)] p-4 flex items-center gap-4"
            >
              <div className="w-11 h-11 rounded-xl border flex items-center justify-center shrink-0 bg-violet-500/10 border-violet-500/20 text-violet-600 dark:text-violet-400">
                <Plug className="w-5 h-5" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <p className="text-[15px] font-semibold text-[var(--text-1)] truncate">
                    {installation.team_name ?? installation.team_id}
                  </p>
                  <StatusIndicator status={installation.is_enabled ? 'active' : 'inactive'} pulse={installation.is_enabled} />
                  {installation.source_type && (
                    <Badge variant="neutral" className="text-[10px] shrink-0 gap-1">
                      {installation.source_type === 'supervisor' ? <Users className="w-2.5 h-2.5" /> : <Bot className="w-2.5 h-2.5" />}
                      {installation.source_type === 'supervisor' ? 'Multi-agent (supervisor)' : 'Single agent'}
                    </Badge>
                  )}
                </div>
                <p className="text-[11px] text-[var(--text-3)] mt-1">
                  {installation.is_linked ? 'Connected' : 'Setup not finished yet'}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button variant="outline" size="xs" onClick={() => handleToggleEnabled(installation)}>
                  {installation.is_enabled ? 'Disable' : 'Enable'}
                </Button>
                <Button variant="outline" size="xs" onClick={() => setRebindTarget(installation)} disabled={!installation.is_linked}>
                  Rebind
                </Button>
                <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(installation)} title="Disconnect">
                  <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {rebindTarget && (
        <RebindDialog
          installation={rebindTarget}
          organizationId={organizationId}
          onClose={() => setRebindTarget(null)}
          onSaved={updated => {
            setInstallations(prev => prev.map(i => (i.id === updated.id ? updated : i)))
            setRebindTarget(null)
          }}
        />
      )}

      <Dialog
        open={!!deleteTarget}
        onOpenChange={open => !open && setDeleteTarget(null)}
        title="Disconnect Slack workspace"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDeleteConfirmed} disabled={deleting}>
              {deleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Disconnect
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Disconnect <strong>{deleteTarget?.team_name ?? deleteTarget?.team_id}</strong>? One-AI will stop replying
          in that Slack workspace immediately. This cannot be undone.
        </p>
      </Dialog>
    </>
  )
}
