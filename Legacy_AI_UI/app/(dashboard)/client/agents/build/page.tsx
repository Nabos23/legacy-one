'use client'

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { AnimatePresence, motion } from 'motion/react'
import { AlertCircle, Bot, Check, Loader2, LogIn, Send, Sparkles, X } from 'lucide-react'
import { agentBuilderApi, agentsApi, connectorsApi, dbConnectionsApi, mcpApi, promptGeneratorApi, teamsApi, toolsApi, type AgentBlueprint, type BuilderOption } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { IconTile } from '@/components/ui/icon-tile'
import { Loader } from '@/components/ui/loader'
import { TypingIndicator } from '@/components/ui/typing-indicator'
import { ConnectorSetupDialog } from '@/components/connectors/connector-setup-dialog'
import { AgentBuilderPopup, type BuilderStep, type OwnerScope } from '@/components/agents/agent-builder-popup'
import { cn } from '@/lib/utils'
import type { ConnectorRegistryItem } from '@/types/connectors'
import type { DbConnectionPublic, TeamPublic } from '@/types'

const PROMPT_KEY = 'one_ai_builder_prompt'
const EASE = [0.16, 1, 0.3, 1] as const
const MIN_STEP_DWELL_MS = 3500
type Message = { id: string; role: 'user' | 'assistant'; text: string; status?: 'working' | 'done' | 'error' }

export default function ConversationalAgentBuilderPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const { toast } = useToast()
  const started = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [prompt, setPrompt] = useState('')
  const [draft, setDraft] = useState('')
  const [blueprint, setBlueprint] = useState<AgentBlueprint | null>(null)
  const [dismissedStep, setDismissedStep] = useState<BuilderStep | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [creatingStage, setCreatingStage] = useState('')
  const [createdId, setCreatedId] = useState<string | null>(null)
  const [connected, setConnected] = useState<Record<string, boolean>>({})
  const [dbConnections, setDbConnections] = useState<DbConnectionPublic[] | null>(null)
  const [dbConnectionsLoading, setDbConnectionsLoading] = useState(false)
  const [selectedDbConnId, setSelectedDbConnId] = useState<string | null>(null)
  const [skippedConnectorIds, setSkippedConnectorIds] = useState<string[]>([])
  const [dbSkipped, setDbSkipped] = useState(false)
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({})
  const [unmatchedAcknowledged, setUnmatchedAcknowledged] = useState(false)
  const [selectedSubstitutes, setSelectedSubstitutes] = useState<string[]>([])
  const [registry, setRegistry] = useState<ConnectorRegistryItem[] | null>(null)
  const [setupConnectorId, setSetupConnectorId] = useState<string | null>(null)
  const [pendingResume, setPendingResume] = useState<string | null>(null)
  const [anonGateStep, setAnonGateStep] = useState<'building' | 'gate' | null>(null)
  const [ownerScope, setOwnerScope] = useState<OwnerScope>('user')
  const [scopeSelectedValue, setScopeSelectedValue] = useState<OwnerScope | null>(null)
  const [scopeChosen, setScopeChosen] = useState(false)
  const [teamId, setTeamId] = useState<string | null>(null)
  const [teams, setTeams] = useState<TeamPublic[] | null>(null)
  const [teamsLoading, setTeamsLoading] = useState(false)
  const scopeAsked = useRef(false)

  const isSuperAdmin = user?.role === 'super_admin' || user?.role === 'super admin'
  const isOrgAdmin = user?.role === 'org_admin' || user?.role === 'org admin' || user?.role === 'admin'
  const isOrgManager = user?.role === 'org_manager' || user?.role === 'org manager'
  const canChooseScope = isSuperAdmin || isOrgAdmin || isOrgManager

  const question = blueprint?.questions[0]
  const hasUnmatched = (blueprint?.unmatched_capabilities.length ?? 0) > 0
  const pastMissingTools = !hasUnmatched || unmatchedAcknowledged
  const needsMissingToolsAck = !!blueprint && !question && hasUnmatched && !unmatchedAcknowledged
  const integrationsReady = (blueprint?.connector_ids.every(id => connected[id] || skippedConnectorIds.includes(id)) ?? false) && (!blueprint?.requires_db_connection || !!selectedDbConnId || dbSkipped)
  const setupConnector = registry?.find(c => c.id === setupConnectorId) ?? null
  const readyForScope = !!blueprint && !question && pastMissingTools && integrationsReady
  const needsIntegrations = !!blueprint && !question && pastMissingTools && !integrationsReady
  const needsScope = readyForScope && canChooseScope && !scopeSelectedValue
  const needsTeam = scopeSelectedValue === 'team' && !scopeChosen
  const readyToCreate = !!blueprint && !question && scopeChosen && !createdId && !creating
  const currentStep: BuilderStep | null = creating
    ? 'creating'
    : question
      ? 'question'
      : needsMissingToolsAck
        ? 'missing-tools'
        : needsIntegrations
          ? 'integrations'
          : needsScope
            ? 'scope'
            : needsTeam
              ? 'team'
              : readyToCreate
                ? 'create'
                : null
  const currentStepKey = currentStep === 'question' && question ? `question:${question.id}` : currentStep

  const [displayedStep, setDisplayedStep] = useState<BuilderStep | null>(null)
  const [displayedBlueprint, setDisplayedBlueprint] = useState<AgentBlueprint | null>(null)
  const displayedStepKey = useRef<string | null>(null)
  const stepShownAt = useRef(0)

  useEffect(() => {
    if (currentStepKey === displayedStepKey.current) return
    const commit = () => {
      setDisplayedStep(currentStep)
      setDisplayedBlueprint(blueprint)
      displayedStepKey.current = currentStepKey
      stepShownAt.current = Date.now()
    }
    if (displayedStepKey.current === null || currentStep === null) { commit(); return }
    const remaining = Math.max(0, MIN_STEP_DWELL_MS - (Date.now() - stepShownAt.current))
    const t = setTimeout(commit, remaining)
    return () => clearTimeout(t)
  }, [currentStepKey, currentStep, blueprint])

  const displayedQuestion = displayedStep === 'question' ? displayedBlueprint?.questions[0] : undefined
  const popupOpen = !!displayedStep && dismissedStep !== displayedStep

  const say = (text: string, status?: Message['status']) => {
    const id = crypto.randomUUID()
    setMessages(current => [...current, { id, role: 'assistant', text, status }])
    return id
  }

  const updateMessage = (id: string, patch: Partial<Message>) =>
    setMessages(current => current.map(m => m.id === id ? { ...m, ...patch } : m))

  const describeNextSteps = (bp: AgentBlueprint) => {
    const needsConnectors = bp.connector_names.length > 0
    const needsDb = bp.requires_db_connection
    if (needsConnectors && needsDb) return `This agent needs ${bp.connector_names.join(', ')} and a database connection. Connect them below, then I’ll build it.`
    if (needsConnectors) return `This agent needs ${bp.connector_names.join(', ')}. Connect the account below, then I’ll build it.`
    if (needsDb) return 'This agent needs a database connection — pick one you already have, or connect a new one below.'
    return 'Everything is ready. Review the plan and create your agent.'
  }

  // Merges user-picked substitutes (from the "missing tools" popup) directly
  // into the blueprint's tool/connector/mcp lists — no extra LLM round-trip.
  const applySubstitutes = (bp: AgentBlueprint, values: string[]): AgentBlueprint => {
    const next = { ...bp }
    for (const value of values) {
      const option = bp.available_options.find(o => o.value === value)
      if (!option) continue
      const sep = option.value.indexOf(':')
      const kind = option.value.slice(0, sep)
      const id = option.value.slice(sep + 1)
      if (kind === 'connector' && !next.connector_ids.includes(id)) {
        next.connector_ids = [...next.connector_ids, id]
        next.connector_names = [...next.connector_names, option.label]
      } else if (kind === 'tool' && !next.tool_ids.includes(id)) {
        next.tool_ids = [...next.tool_ids, id]
        next.tool_names = [...next.tool_names, option.label]
      } else if (kind === 'mcp' && !next.mcp_registry_keys.includes(id)) {
        next.mcp_registry_keys = [...next.mcp_registry_keys, id]
        next.mcp_names = [...next.mcp_names, option.label]
      }
    }
    return next
  }

  const toggleSubstitute = (value: string) =>
    setSelectedSubstitutes(current => current.includes(value) ? current.filter(v => v !== value) : [...current, value])

  const continueAfterMissingTools = () => {
    if (!blueprint) return
    const merged = selectedSubstitutes.length ? applySubstitutes(blueprint, selectedSubstitutes) : blueprint
    if (selectedSubstitutes.length) {
      const pickedLabels = selectedSubstitutes.map(v => blueprint.available_options.find(o => o.value === v)?.label).filter((l): l is string => !!l)
      if (pickedLabels.length) setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', text: pickedLabels.join(', ') }])
      setBlueprint(merged)
    }
    setUnmatchedAcknowledged(true)
    say(describeNextSteps(merged), 'done')
  }

  const declineCreate = () => {
    setUnmatchedAcknowledged(false)
    setSelectedSubstitutes([])
    setBlueprint(null)
    setDismissedStep(null)
    say('No problem — tell me more about what you need and I’ll adjust the plan.', 'done')
  }

  const analyze = async (value: string, nextAnswers = answers) => {
    setBusy(true)
    const workingId = say('Understanding your goal and matching the right tools…', 'working')
    try {
      const result = await agentBuilderApi.blueprint(value, nextAnswers)
      const [statuses, dbList] = await Promise.all([
        Promise.all(result.connector_ids.map(async id => [id, (await connectorsApi.getStatus(id).catch(() => ({ connected: false }))).connected] as const)),
        result.requires_db_connection && user
          ? dbConnectionsApi.listByOrg(user.organization_id, 1, 50).then(p => p.items).catch(() => [])
          : Promise.resolve(null),
      ])
      // Commit blueprint + connector/db status together so the popup never renders
      // a transient step computed from a new blueprint paired with stale connection state.
      setBlueprint(result)
      setConnected(Object.fromEntries(statuses))
      setDbConnections(dbList)
      setSelectedDbConnId(null)
      setDismissedStep(null)
      setUnmatchedAcknowledged(false)
      setSelectedSubstitutes([])
      updateMessage(workingId, { text: `Blueprint ready: ${result.name}`, status: 'done' })
      if (result.questions.length) say(result.questions[0].text)
      else if (result.unmatched_capabilities.length) say(`I couldn’t find ${result.unmatched_capabilities.join(', ')} in our tools. Pick a replacement below, or continue without it.`)
      else say(describeNextSteps(result))
    } catch (error) {
      updateMessage(workingId, { text: error instanceof Error ? error.message : 'I could not prepare the blueprint.', status: 'error' })
    } finally { setBusy(false) }
  }

  useEffect(() => {
    if (authLoading || !user || started.current) return
    started.current = true
    const saved = sessionStorage.getItem(PROMPT_KEY) || ''
    if (saved) setPendingResume(saved)
  }, [authLoading, user])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, blueprint?.questions])

  useEffect(() => {
    if (anonGateStep !== 'building') return
    const timer = setTimeout(() => setAnonGateStep('gate'), 1600)
    return () => clearTimeout(timer)
  }, [anonGateStep])

  useEffect(() => {
    if (!readyForScope || scopeAsked.current) return
    scopeAsked.current = true
    if (canChooseScope) say('Who should be able to use this agent?')
    else setScopeChosen(true)
  }, [readyForScope, canChooseScope])

  const chooseScope = async (value: OwnerScope, label: string) => {
    setScopeSelectedValue(value)
    setOwnerScope(value)
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', text: label }])
    if (value !== 'team') {
      say(value === 'user' ? 'Got it — this agent will be personal to you.' : 'Got it — this agent will be visible to everyone in the organization.', 'done')
      setScopeChosen(true)
      return
    }
    if (!user) return
    setTeamsLoading(true)
    const workingId = say('Looking up your teams…', 'working')
    try {
      const result = await teamsApi.listByOrg(user.organization_id, 1, 100)
      if (!result.items.length) {
        updateMessage(workingId, { text: 'No teams yet in your organization — I’ll make this agent visible to everyone in the org instead.', status: 'done' })
        setOwnerScope('organization')
        setScopeChosen(true)
      } else {
        setTeams(result.items)
        updateMessage(workingId, { text: 'Which team should have access?', status: 'done' })
      }
    } catch {
      updateMessage(workingId, { text: 'Could not load teams — I’ll make this agent visible to everyone in the org instead.', status: 'error' })
      setOwnerScope('organization')
      setScopeChosen(true)
    } finally { setTeamsLoading(false) }
  }

  const chooseTeam = (id: string, name: string) => {
    setTeamId(id)
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', text: name }])
    say(`Got it — only members of ${name} will have access.`, 'done')
    setScopeChosen(true)
  }

  const resumePending = () => {
    if (!pendingResume) return
    const value = pendingResume
    setPrompt(value)
    setPendingResume(null)
    setMessages([{ id: crypto.randomUUID(), role: 'user', text: value }])
    void analyze(value, {})
  }

  const discardPending = () => {
    sessionStorage.removeItem(PROMPT_KEY)
    setPendingResume(null)
  }

  const choose = async (questionId: string, value: string, label: string) => {
    setSelectedOptions(current => ({ ...current, [questionId]: value }))
    const next = { ...answers, [questionId]: value, integration: value }
    setAnswers(next)
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', text: label }])
    await analyze(prompt, next)
  }

  const openConnectorSetup = async (id: string) => {
    if (!registry) {
      try {
        setRegistry(await connectorsApi.getRegistry())
      } catch {
        say('Could not load connector details. Try the Connectors page instead.', 'error')
        return
      }
    }
    setSetupConnectorId(id)
  }

  const authorizeConnector = (id: string, name: string, url: string) => {
    window.open(url, 'connector-auth', 'width=560,height=720')
    const workingId = say(`Complete ${name} authorization in the new window — I’ll detect it automatically.`, 'working')
    void (async () => {
      for (let attempt = 0; attempt < 60; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 2000))
        const status = await connectorsApi.getStatus(id).catch(() => null)
        if (status?.connected) { setConnected(c => ({ ...c, [id]: true })); updateMessage(workingId, { text: `${name} connected successfully.`, status: 'done' }); return }
      }
      updateMessage(workingId, { text: `${name} connection is still pending — you can try again if authorization didn’t complete.`, status: 'error' })
    })()
  }

  const skipConnector = (id: string) => {
    const name = blueprint?.connector_names[blueprint.connector_ids.indexOf(id)] || 'that service'
    setSkippedConnectorIds(current => current.includes(id) ? current : [...current, id])
    say(`Skipping ${name} — you can connect it later from Connectors.`, 'done')
  }

  const skipDbConnection = () => {
    setDbSkipped(true)
    say('Skipping the database connection — you can add one later.', 'done')
  }

  const unskipDb = () => setDbSkipped(false)

  const selectDbConnection = (id: string, name: string) => {
    setSelectedDbConnId(id)
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', text: name }])
    say('Got it — this agent will query that database.', 'done')
  }

  const createDbConnection = () => {
    if (!user) return
    window.open('/client/db-connections/create', 'db-connection-setup', 'width=720,height=800')
    const workingId = say('Complete the database connection in the new window — I’ll detect it automatically.', 'working')
    const priorCount = dbConnections?.length ?? 0
    setDbConnectionsLoading(true)
    void (async () => {
      for (let attempt = 0; attempt < 60; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 2000))
        const items = await dbConnectionsApi.listByOrg(user.organization_id, 1, 50).then(p => p.items).catch(() => null)
        if (items && items.length > priorCount) {
          setDbConnections(items)
          setDbConnectionsLoading(false)
          const newest = items[items.length - 1]
          setSelectedDbConnId(newest.id ?? null)
          updateMessage(workingId, { text: 'Database connected successfully.', status: 'done' })
          return
        }
      }
      setDbConnectionsLoading(false)
      updateMessage(workingId, { text: 'Database connection is still pending — you can try again if setup didn’t complete.', status: 'error' })
    })()
  }

  const create = async () => {
    if (!blueprint || !user) return
    // Skipped connectors were never authorized — only bind the ones the user actually connected.
    const connectedConnectorIds = blueprint.connector_ids.filter(id => connected[id])
    setBusy(true)
    setCreating(true)
    setCreatingStage('Creating your agent…')
    try {
      const agent = await agentsApi.create({ organization_id: user.organization_id, name: blueprint.name, description: blueprint.description, prompt: blueprint.system_prompt, guardrails: blueprint.guardrails, connector_ids: connectedConnectorIds, mcp_server_ids: [], owner_scope: ownerScope, team_id: ownerScope === 'team' && teamId ? teamId : undefined })
      setCreatedId(agent.id!)

      // Blueprint tool_ids are tool_registry catalog IDs. Agent.tool_ids must
      // instead reference org-scoped `tools` collection instances (the same
      // shape backend/agent/services.py._auto_assign_default_tools creates),
      // so each catalog tool needs its own instance created and bound here —
      // otherwise chat/services.py silently drops it (tool_doc lookup misses).
      if (blueprint.tool_ids.length) {
        setCreatingStage('Attaching tools…')
        const createdTools = await Promise.all(blueprint.tool_ids.map((toolId, index) => {
          const name = blueprint.tool_names[index] || 'Tool'
          const isDbTool = blueprint.db_tool_ids.includes(toolId)
          return toolsApi.create({
            organization_id: user.organization_id,
            agent_id: agent.id!,
            tool_id: toolId,
            name,
            user_description: `${name} tool for this agent`,
            db_conn_id: isDbTool ? selectedDbConnId ?? undefined : undefined,
          })
        }))
        await agentsApi.update(agent.id!, { tool_ids: [...(agent.tool_ids ?? []), ...createdTools.map(t => t.id!)] })
      }

      if (blueprint.mcp_registry_keys.length) {
        setCreatingStage('Configuring MCP tools…')
        for (const key of blueprint.mcp_registry_keys) await mcpApi.create({ organization_id: user.organization_id, agent_id: agent.id!, registry_key: key })
      }
      const generated = await promptGeneratorApi.generateForAgent(agent.id!)
      await agentsApi.update(agent.id!, {
        prompt: generated.prompt,
        guardrails: generated.guardrails || undefined,
        connector_ids: connectedConnectorIds,
        is_active: true,
      })
      sessionStorage.removeItem(PROMPT_KEY)
      toast.success(`${blueprint.name} is ready to use.`, 'Agent created')
      router.push('/client/agents')
    } catch (error) {
      setCreating(false)
      setBusy(false)
      say(error instanceof Error ? error.message : 'Agent creation failed. Your draft is safe.', 'error')
    }
  }

  const submitPrompt = async () => {
    const value = draft.trim()
    if (value.length < 10) return
    sessionStorage.setItem(PROMPT_KEY, value)
    setPrompt(value); setBlueprint(null); setDismissedStep(null); setAnswers({}); setCreatedId(null); setDraft('')
    setOwnerScope('user'); setScopeSelectedValue(null); setScopeChosen(false); setTeamId(null); setTeams(null)
    setDbConnections(null); setSelectedDbConnId(null); setDbConnectionsLoading(false)
    setSkippedConnectorIds([]); setDbSkipped(false)
    scopeAsked.current = false
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', text: value }])
    await analyze(value, {})
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!busy && draft.trim().length >= 10) void submitPrompt()
    }
  }

  const submitPromptAnon = () => {
    const value = draft.trim()
    if (value.length < 10) return
    sessionStorage.setItem(PROMPT_KEY, value)
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', text: value }])
    setDraft('')
    setAnonGateStep('building')
  }

  const handleAnonKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (draft.trim().length >= 10) submitPromptAnon()
    }
  }

  if (!authLoading && !user) {
    const submitted = messages.length > 0
    return <PageShell>
      <ChatShell>
        <BuilderHeader />
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.length === 0 && (
            <div className="flex items-start gap-2.5">
              <AssistantAvatar />
              <div className="max-w-[70%] animate-slideInLeft rounded-2xl rounded-bl-sm border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3 text-sm">
                Describe the agent you want to build, and I’ll get it ready for you.
              </div>
            </div>
          )}
          {messages.map(message => (
            <div key={message.id} className={cn('flex items-start gap-2.5', message.role === 'user' ? 'justify-end' : 'justify-start')}>
              {message.role === 'assistant' && <AssistantAvatar />}
              <div className={cn(
                'max-w-[70%] animate-slideInLeft rounded-2xl px-4 py-3 text-sm',
                message.role === 'user'
                  ? 'animate-slideInRight rounded-br-sm bg-violet-600 text-white shadow-[0_8px_24px_-8px_rgba(124,58,237,0.5)]'
                  : 'border border-[var(--border)] bg-[var(--surface-2)] rounded-bl-sm'
              )}>
                {message.text}
              </div>
            </div>
          ))}
        </div>
        {submitted ? (
          <div className="flex justify-center gap-3 border-t border-[var(--border)] p-4">
            <Button nativeButton={false} render={<Link href="/login?from=/client/agents/build" />}><LogIn className="mr-2 size-4" />Log in</Button>
            <Button variant="outline" nativeButton={false} render={<Link href="/register?from=/client/agents/build" />}>Sign up</Button>
          </div>
        ) : (
          <div className="flex gap-2 border-t border-[var(--border)] p-4">
            <textarea
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={handleAnonKeyDown}
              placeholder="Describe the agent you want to build…"
              className="min-h-12 flex-1 resize-none rounded-xl border border-[var(--border-2)] bg-[var(--surface)] p-3 text-sm outline-none transition-shadow duration-150 focus:border-violet-500 focus:ring-4 focus:ring-violet-500/10"
            />
            <motion.div whileTap={{ scale: 0.94 }}>
              <Button size="icon-lg" variant="primary" onClick={submitPromptAnon} disabled={draft.trim().length < 10} className="h-full shadow-[0_8px_20px_-8px_rgba(124,58,237,0.55)]">
                <Send className="size-4" />
              </Button>
            </motion.div>
          </div>
        )}
      </ChatShell>
      <AnimatePresence>
        {anonGateStep && <AnonGateModal step={anonGateStep} onClose={() => setAnonGateStep(null)} />}
      </AnimatePresence>
    </PageShell>
  }

  if (pendingResume) {
    return <PageShell>
      <ChatShell className="items-center justify-center gap-4 p-8 text-center">
        <div className="relative">
          <div className="absolute inset-0 -z-10 animate-glowPulse rounded-3xl" />
          <IconTile icon={Bot} size="lg" className="animate-floatY" />
        </div>
        <div>
          <h1 className="text-h3">Resume your last agent request?</h1>
          <p className="mt-2 max-w-md text-sm text-[var(--text-3)]">“{pendingResume}”</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={resumePending}>Resume</Button>
          <Button variant="outline" onClick={discardPending}>Discard &amp; start new</Button>
        </div>
      </ChatShell>
    </PageShell>
  }

  return <PageShell>
    <ChatShell>
      <BuilderHeader busy={busy} />
      <div ref={scrollRef} className="custom-scrollbar min-h-0 flex-1 space-y-4 overflow-y-auto p-6">
        <AnimatePresence initial={false}>
          {messages.map(message => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.3, ease: EASE }}
              className={cn('flex items-start gap-2.5', message.role === 'user' ? 'justify-end' : 'justify-start')}
            >
              {message.role === 'assistant' && (
                message.status === 'working' ? (
                  <motion.div
                    animate={{ y: [0, -3, 0] }}
                    transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                    className="relative mt-0.5 shrink-0"
                  >
                    <div className="absolute inset-0 -z-10 animate-glowPulse rounded-lg" aria-hidden />
                    <IconTile icon={Bot} size="sm" />
                  </motion.div>
                ) : <AssistantAvatar />
              )}
              <div className={cn(
                'max-w-[70%] rounded-2xl px-4 py-3 text-sm',
                message.role === 'user'
                  ? 'rounded-br-sm bg-violet-600 text-white shadow-[0_8px_24px_-8px_rgba(124,58,237,0.5)]'
                  : message.status === 'error'
                    ? 'rounded-bl-sm border border-red-500/30 bg-red-500/5 text-[var(--text-1)]'
                    : message.status === 'working'
                      ? 'rounded-bl-sm border border-violet-500/20 bg-violet-500/[0.04] shadow-[0_4px_16px_-8px_rgba(124,58,237,0.35)]'
                      : 'rounded-bl-sm border border-[var(--border)] bg-[var(--surface-2)]'
              )}>
                {message.status === 'working' ? (
                  <div className="flex items-center gap-2">
                    <motion.span
                      animate={{ rotate: 360 }}
                      transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                      className="shrink-0"
                    >
                      <Sparkles className="size-3.5 text-violet-500" />
                    </motion.span>
                    <motion.span
                      animate={{ backgroundPositionX: ['150%', '-50%'] }}
                      transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }}
                      className="bg-clip-text font-medium text-transparent [background-image:linear-gradient(90deg,var(--text-2)_0%,var(--text-2)_40%,#a78bfa_50%,var(--text-2)_60%,var(--text-2)_100%)] [background-size:250%_100%]"
                    >
                      {message.text}
                    </motion.span>
                  </div>
                ) : (
                  <span className="align-middle">
                    {message.status === 'done' && <Check className="mr-1.5 inline size-4 text-emerald-500" />}
                    {message.status === 'error' && <AlertCircle className="mr-1.5 inline size-4 text-red-500" />}
                    {message.text}
                  </span>
                )}
                {message.status === 'working' && <TypingIndicator className="mt-2" />}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {currentStep && !popupOpen && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: EASE }} className="pl-9">
            <Button size="sm" variant="outline" onClick={() => setDismissedStep(null)}>
              <Sparkles className="mr-2 size-3.5" />Resume setup
            </Button>
          </motion.div>
        )}
      </div>
      <div className="flex gap-2 border-t border-[var(--border)] p-4">
        <textarea
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={busy}
          placeholder={messages.length === 0 ? 'Describe the agent you want to build…' : 'Describe another agent…'}
          className="min-h-12 flex-1 resize-none rounded-xl border border-[var(--border-2)] bg-[var(--surface)] p-3 text-sm outline-none transition-shadow duration-150 focus:border-violet-500 focus:ring-4 focus:ring-violet-500/10 disabled:opacity-60"
        />
        <motion.div whileTap={{ scale: 0.94 }}>
          <Button size="icon-lg" variant="primary" onClick={submitPrompt} disabled={busy || draft.trim().length < 10} className="h-full shadow-[0_8px_20px_-8px_rgba(124,58,237,0.55)]">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          </Button>
        </motion.div>
      </div>
    </ChatShell>

    <AnimatePresence>
      {popupOpen && displayedBlueprint && displayedStep && (
        <AgentBuilderPopup
          blueprint={displayedBlueprint}
          step={displayedStep}
          busy={busy}
          onClose={() => setDismissedStep(displayedStep)}
          question={displayedQuestion}
          selectedValue={displayedQuestion ? selectedOptions[displayedQuestion.id] : undefined}
          onChooseOption={choose}
          selectedSubstitutes={selectedSubstitutes}
          onToggleSubstitute={toggleSubstitute}
          onContinueAfterMissingTools={continueAfterMissingTools}
          onDeclineCreate={declineCreate}
          connected={connected}
          onConnectConnector={openConnectorSetup}
          skippedConnectorIds={skippedConnectorIds}
          onSkipConnector={skipConnector}
          dbConnections={dbConnections}
          dbConnectionsLoading={dbConnectionsLoading}
          selectedDbConnId={selectedDbConnId}
          onSelectDbConnection={selectDbConnection}
          onCreateDbConnection={createDbConnection}
          dbSkipped={dbSkipped}
          onSkipDb={skipDbConnection}
          onUndoSkipDb={unskipDb}
          scopeSelectedValue={scopeSelectedValue}
          onChooseScope={chooseScope}
          teams={teams}
          teamsLoading={teamsLoading}
          teamId={teamId}
          onChooseTeam={chooseTeam}
          onCreate={create}
          creatingStage={creatingStage}
        />
      )}
    </AnimatePresence>

    {setupConnector && <ConnectorSetupDialog
      connector={setupConnector}
      status={null}
      open
      onOpenChange={open => !open && setSetupConnectorId(null)}
      onConnected={() => { setConnected(c => ({ ...c, [setupConnector.id]: true })); say(`${setupConnector.name} connected successfully.`, 'done'); setSetupConnectorId(null) }}
      onAuthorize={url => authorizeConnector(setupConnector.id, setupConnector.name, url)}
    />}
  </PageShell>
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex h-full min-h-0 flex-1 flex-col p-4">
      <div className="pointer-events-none absolute -top-10 left-10 -z-10 size-72 rounded-full bg-violet-500/10 blur-[100px]" aria-hidden />
      <div className="pointer-events-none absolute -bottom-10 right-10 -z-10 size-72 rounded-full bg-indigo-500/10 blur-[100px]" aria-hidden />
      {children}
    </div>
  )
}

function ChatShell({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn('glass flex h-full min-h-0 flex-1 flex-col rounded-2xl', className)}>{children}</section>
}

function BuilderHeader({ busy }: { busy?: boolean }) {
  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] p-5">
      <div className="relative">
        {busy && <div className="absolute inset-0 -z-10 animate-glowPulse rounded-xl" aria-hidden />}
        <IconTile icon={Bot} />
      </div>
      <div>
        <h1 className="text-h4">Build an agent with AI</h1>
        <p className="text-xs text-[var(--text-3)]">I’ll ask questions, connect services, and show every API step.</p>
      </div>
    </header>
  )
}

function AssistantAvatar() {
  return <IconTile icon={Bot} size="sm" className="mt-0.5" />
}

function AnonGateModal({ step, onClose }: { step: 'building' | 'gate'; onClose: () => void }) {
  return createPortal(
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25, ease: EASE }}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label={step === 'building' ? 'Development started' : 'Log in to continue'}
          initial={{ opacity: 0, scale: 0.85, y: 28 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 16 }}
          transition={{ type: 'spring', stiffness: 300, damping: 24 }}
          className="glass-card relative w-full max-w-md overflow-hidden rounded-3xl border border-violet-500/20 bg-card/95 p-8 text-center shadow-[0_24px_64px_-16px_rgba(124,58,237,0.45)] backdrop-blur-2xl backdrop-saturate-150"
        >
          <div className="pointer-events-none absolute -top-16 -left-16 -z-10 size-56 rounded-full bg-violet-500/20 blur-[80px]" aria-hidden />
          <div className="pointer-events-none absolute -bottom-16 -right-16 -z-10 size-56 rounded-full bg-indigo-500/20 blur-[80px]" aria-hidden />

          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute right-4 top-4 flex size-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>

          <AnimatePresence mode="wait">
            {step === 'building' ? (
              <motion.div key="building" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="flex flex-col items-center gap-3">
                <Loader size={72} />
                <p className="text-sm font-semibold">Development started</p>
                <p className="text-xs text-[var(--text-3)]">Analyzing your request…</p>
              </motion.div>
            ) : (
              <motion.div key="gate" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25, ease: EASE }} className="flex flex-col items-center gap-4">
                <IconTile icon={Bot} size="lg" />
                <div>
                  <h2 className="text-h4 font-semibold">Log in to keep building</h2>
                  <p className="mt-2 text-sm text-[var(--text-3)]">Create a free account (or log in) to see this agent get built — connect services and create it. Your request is saved, nothing is lost.</p>
                </div>
                <div className="flex w-full gap-3">
                  <Button className="flex-1" nativeButton={false} render={<Link href="/login?from=/client/agents/build" />}><LogIn className="mr-2 size-4" />Log in</Button>
                  <Button variant="outline" className="flex-1" nativeButton={false} render={<Link href="/register?from=/client/agents/build" />}>Sign up</Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </>,
    document.body,
  )
}
