'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Bot, CheckCircle2, Loader2, LogIn, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { InfoBox } from '@/components/ui/info-box'
import { Logo } from '@/components/landing/logo'
import { useAuth } from '@/contexts/auth-context'
import { agentsApi, connectorAppsApi, organizationsApi } from '@/lib/api'
import type { SlackAppSourceType } from '@/lib/api'
import type { AgentPublic, OrganizationPublic } from '@/types'

type PageState = 'loading' | 'need-login' | 'invalid' | 'already-linked' | 'form' | 'success'

/** "Finish setup" page for our Slack App -- reached from the DM link sent
 * right after OAuth install (see backend/connector_apps/slack/services.py's
 * _dm_finish_setup_link). Binds the pending installation to the visitor's
 * One-AI org + an agent. Deliberately outside the (dashboard) route group:
 * an anonymous, just-installed Slack user may not have a One-AI session yet
 * (see app/(integrations)/layout.tsx -- no auth gate at the layout level,
 * only proxy.ts's /admin|/client guard, which this path doesn't match). */
export default function SlackLinkPage() {
  const { user, isAuthenticated, loading: authLoading, permissions } = useAuth()

  const [installationId, setInstallationId] = useState('')
  const [token, setToken] = useState('')
  const [state, setState] = useState<PageState>('loading')
  const [teamName, setTeamName] = useState<string | null>(null)
  const [error, setError] = useState('')

  const [sourceType, setSourceType] = useState<SlackAppSourceType>('supervisor')
  const [agentId, setAgentId] = useState('')
  const [agents, setAgents] = useState<AgentPublic[]>([])
  const [submitting, setSubmitting] = useState(false)

  const isSuperAdmin = !!permissions?.is_super_admin
  const [orgs, setOrgs] = useState<OrganizationPublic[]>([])
  const [organizationId, setOrganizationId] = useState('')

  // Deliberately NOT the useOrganizations() hook: it fires an authenticated
  // /organizations call unconditionally on mount, and calling that while
  // logged out trips the global 401 handler (lib/api/client.ts), which hard-
  // redirects to a bare /login BEFORE this page's own "log in first" state
  // ever gets a chance to render (with no `from` param, losing the
  // installation_id/token this whole page exists to carry through). Only
  // fetch orgs once we know there's a real session, and only for the one
  // case that needs the list (a super admin choosing which org to bind to).
  useEffect(() => {
    if (!isAuthenticated || !isSuperAdmin) return
    organizationsApi.list(1, 100).then(res => setOrgs(res.items))
  }, [isAuthenticated, isSuperAdmin])

  // Read installation_id/token from the URL without useSearchParams, so this
  // page doesn't need a Suspense boundary (same reasoning as the widget
  // preview page elsewhere in this app).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setInstallationId(params.get('installation_id') ?? '')
    setToken(params.get('token') ?? '')
  }, [])

  useEffect(() => {
    if (!installationId || !token) return
    if (authLoading) return
    if (!isAuthenticated) {
      setState('need-login')
      return
    }
    connectorAppsApi.slack
      .getPending(installationId, token)
      .then(info => {
        setTeamName(info.team_name ?? null)
        setState(info.already_linked ? 'already-linked' : 'form')
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'This link is invalid or has expired.')
        setState('invalid')
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [installationId, token, isAuthenticated, authLoading])

  useEffect(() => {
    if (!isAuthenticated) return
    const effectiveOrgId = isSuperAdmin ? organizationId : (user?.organization_id ?? '')
    if (!effectiveOrgId) { setAgents([]); return }
    agentsApi.listByOrg(effectiveOrgId, 1, 100, undefined, { isActive: true }).then(res => setAgents(res.items))
    setAgentId('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuperAdmin, organizationId, user?.organization_id, isAuthenticated])

  useEffect(() => {
    if (!isSuperAdmin && user?.organization_id) setOrganizationId(user.organization_id)
  }, [isSuperAdmin, user?.organization_id])

  const handleLogin = () => {
    const here = `${window.location.pathname}${window.location.search}`
    window.location.href = `/login?from=${encodeURIComponent(here)}`
  }

  const handleSubmit = async () => {
    setError('')
    if (!organizationId) {
      setError('Select an organization first.')
      return
    }
    if (sourceType === 'single_agent' && !agentId) {
      setError('Select an agent first.')
      return
    }
    setSubmitting(true)
    try {
      await connectorAppsApi.slack.link({
        installation_id: installationId,
        token,
        organization_id: organizationId,
        source_type: sourceType,
        agent_id: sourceType === 'single_agent' ? agentId : undefined,
      })
      setState('success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to finish setup.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center p-6 bg-background">
      <div className="w-full max-w-[440px]">
        <Link href="/" aria-label="ONE-AI home" className="inline-flex mb-8">
          <Logo />
        </Link>

        {(state === 'loading' || authLoading) && (
          <div className="flex items-center gap-2 text-[14px] text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            Checking your link…
          </div>
        )}

        {state === 'need-login' && (
          <div>
            <h1 className="text-[22px] font-bold text-foreground tracking-tight">Almost there</h1>
            <p className="mt-2 text-[14.5px] text-muted-foreground leading-relaxed">
              Log into your One-AI account to connect this Slack workspace to an agent.
            </p>
            <Button variant="primary" className="mt-5 w-full h-10" onClick={handleLogin}>
              <LogIn className="w-4 h-4 mr-2" />
              Log in to continue
            </Button>
          </div>
        )}

        {state === 'invalid' && (
          <div>
            <h1 className="text-[22px] font-bold text-foreground tracking-tight">Link expired</h1>
            <p className="mt-2 text-[14.5px] text-muted-foreground leading-relaxed">{error}</p>
            <p className="mt-4 text-[13.5px] text-muted-foreground">
              Reinstall the Slack app to get a fresh link, or contact your One-AI admin.
            </p>
          </div>
        )}

        {state === 'already-linked' && (
          <div>
            <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-emerald-500/12">
              <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h1 className="text-[22px] font-bold text-foreground tracking-tight text-center">Already connected</h1>
            <p className="mt-2 text-[14.5px] text-muted-foreground leading-relaxed text-center">
              {teamName ? `"${teamName}"` : 'This Slack workspace'} is already linked to a One-AI agent. You can
              rebind it from your dashboard&apos;s Connectors page.
            </p>
          </div>
        )}

        {state === 'success' && (
          <div>
            <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-emerald-500/12">
              <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h1 className="text-[22px] font-bold text-foreground tracking-tight text-center">You&apos;re all set!</h1>
            <p className="mt-2 text-[14.5px] text-muted-foreground leading-relaxed text-center">
              Go back to Slack and message One-AI — it&apos;s ready to chat.
            </p>
          </div>
        )}

        {state === 'form' && (
          <div>
            <h1 className="text-[22px] font-bold text-foreground tracking-tight">
              Connect {teamName ? `"${teamName}"` : 'your Slack workspace'}
            </h1>
            <p className="mt-2 text-[14.5px] text-muted-foreground leading-relaxed">
              Pick which agent answers when someone messages One-AI in this Slack workspace.
            </p>

            {isSuperAdmin && (
              <div className="mt-5">
                <label className="text-[12.5px] font-semibold text-foreground/80 block mb-1.5">Organization</label>
                <Select
                  value={organizationId}
                  onValueChange={setOrganizationId}
                  options={orgs.map(o => ({ value: o.id!, label: o.name }))}
                  placeholder="Select an organization"
                />
              </div>
            )}

            <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                  Auto-routes across every active agent in the org.
                </p>
              </button>
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
                  Slack always talks to exactly one agent you pick below.
                </p>
              </button>
            </div>

            {sourceType === 'single_agent' && (
              <div className="mt-4">
                <label className="text-[12.5px] font-semibold text-foreground/80 block mb-1.5">Agent</label>
                <Select
                  value={agentId}
                  onValueChange={setAgentId}
                  options={agents.map(a => ({ value: a.id!, label: a.name }))}
                  placeholder={agents.length === 0 ? 'No active agents in this organization' : 'Select an agent'}
                  disabled={agents.length === 0}
                />
              </div>
            )}

            {error && (
              <div className="mt-4">
                <InfoBox variant="error">{error}</InfoBox>
              </div>
            )}

            <Button variant="primary" className="mt-6 w-full h-10" onClick={handleSubmit} disabled={submitting}>
              {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Connect workspace
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
