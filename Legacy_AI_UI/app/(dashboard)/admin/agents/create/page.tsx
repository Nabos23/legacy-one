'use client'

import { useEffect, useState } from 'react'
import { useOrganizations } from '@/hooks/use-organizations'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Database,
  Loader2,
  Rocket,
  Sparkles,
  Wrench,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { FormField } from '@/components/ui/form-field'
import { PageHeader } from '@/components/ui/page-header'
import { Stepper } from '@/components/ui/stepper'
import { CodeEditor } from '@/components/ui/code-editor'
import { Badge } from '@/components/ui/badge'
import { InfoBox } from '@/components/ui/info-box'
import { useToast } from '@/hooks/use-toast'
import { useToolRegistry } from '@/hooks/use-tool-registry'
import { useDbConnections } from '@/hooks/use-db-connections'
import { useUsers } from '@/hooks/use-users'
import { agentsApi, promptGeneratorApi, toolsApi } from '@/lib/api'
import { cn, formatToolName } from '@/lib/utils'
import { AgentMcpStep } from '@/components/mcp/agent-mcp-step'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import { AgentAvatarPicker, buildAvatarApiPayload, getAvatarDisplayProps, normalizeAvatarSelection, type AgentAvatarSelection } from '@/components/dashboard/agent-avatar-picker'
import { DEFAULT_AGENT_STICKER_ID } from '@/lib/agent-stickers'
import { useAuth } from '@/contexts/auth-context'
import type { AgentAvatarType } from '@/types'

const STEPS = ['Identity', 'Tools', 'MCP Servers', 'Prompt & Guardrails', 'Review']

const PROMPT_TEMPLATES = [
  {
    title: 'Customer Support',
    prompt:
      'You are a helpful customer support agent. Be empathetic, concise, and always aim to resolve issues on the first reply.',
  },
  {
    title: 'Data Analysis',
    prompt:
      'You are a data analyst assistant. Interpret datasets, explain trends clearly, and suggest actionable insights.',
  },
  {
    title: 'Code Review',
    prompt:
      'You are a senior engineer performing code reviews. Focus on correctness, security, readability, and performance.',
  },
  {
    title: 'General Assistant',
    prompt:
      'You are a versatile AI assistant. Answer questions accurately, ask clarifying questions when needed, and stay helpful.',
  },
]

interface FormData {
  name: string
  description: string
  avatarType: AgentAvatarType
  avatarValue: string
  avatarUrl?: string | null
  avatarPreviewUrl?: string | null
  prompt: string
  guardrails: string
  toolIds: string[]
  toolDbConnectionIds: Record<string, string>
  organization_id: string
  ownerScope: 'user' | 'organization' | 'selected_users'
  allowedUserIds: string[]
}

export default function CreateAgentPage() {
  const router = useRouter()
  const { toast } = useToast()
  const { user } = useAuth()
  
  const isSuperAdmin = user?.role === 'super_admin' || user?.role === 'super admin'
  const canChooseVisibility = isSuperAdmin
  const { data: orgsData } = useOrganizations(1, undefined, 1000)
  const orgs = orgsData?.items ?? []

  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false)
  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null)
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [attachedToolIds, setAttachedToolIds] = useState<string[]>([])
  const [toolRecordIdsByRegistryId, setToolRecordIdsByRegistryId] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [toolPermissions, setToolPermissions] = useState<Record<string, boolean>>({})
  const [toolSearch, setToolSearch] = useState('')
  const { data: toolsData } = useToolRegistry(1, 100, { isActive: true, sortBy: 'name', sortOrder: 'asc' })
  const allTools = toolsData?.items ?? []
  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    avatarType: 'sticker',
    avatarValue: DEFAULT_AGENT_STICKER_ID,
    avatarUrl: null,
    avatarPreviewUrl: null,
    prompt: '',
    guardrails: '',
    toolIds: [],
    toolDbConnectionIds: {},
    organization_id: '',
    ownerScope: 'organization',
    allowedUserIds: [],
  })
  const [userSearch, setUserSearch] = useState('')
  const selectedOrganizationId = isSuperAdmin ? formData.organization_id : (user?.organization_id || '')
  const effectiveOwnerScope = canChooseVisibility ? formData.ownerScope : 'user'
  const { data: orgUsersData } = useUsers(1, selectedOrganizationId || undefined, undefined, undefined, 100, {}, canChooseVisibility)
  const orgUsers = (orgUsersData?.items ?? []).filter(u => u.id !== user?.id)
  const filteredOrgUsers = orgUsers.filter(u =>
    `${u.name} ${u.email}`.toLowerCase().includes(userSearch.toLowerCase())
  )
  const { data: dbConnectionsData, loading: dbConnectionsLoading } = useDbConnections(1, selectedOrganizationId || undefined, 100)
  const dbConnections = (dbConnectionsData?.items ?? []).filter(conn => !selectedOrganizationId || conn.organization_id === selectedOrganizationId)
  const dbConnectionLabel = (conn: (typeof dbConnections)[number]) =>
    conn.name?.trim() || conn.connection_string

  const isAskHumanTool = (tool: (typeof allTools)[number]) => {
    const key = `${tool.id ?? ''} ${tool.name} ${tool.type}`.toLowerCase().replace(/[\s-]+/g, '_')
    return key.includes('ask_human') || key.includes('human_in_loop')
  }
  const selectedToolIds = new Set([
    ...formData.toolIds,
    ...allTools.filter(isAskHumanTool).map(tool => tool.id!).filter(Boolean),
  ])

  useEffect(() => {
    if (isSuperAdmin && orgs.length > 0 && !formData.organization_id) {
      setFormData(prev => ({ ...prev, organization_id: orgs[0].id! }))
    }
  }, [isSuperAdmin, orgs, formData.organization_id])

  useEffect(() => {
    const askHumanToolIds = allTools.filter(isAskHumanTool).map(tool => tool.id!).filter(Boolean)
    if (askHumanToolIds.length === 0) return

    setFormData(prev => {
      const nextToolIds = Array.from(new Set([...prev.toolIds, ...askHumanToolIds]))
      return nextToolIds.length === prev.toolIds.length ? prev : { ...prev, toolIds: nextToolIds }
    })
  }, [allTools])

  const update = (patch: Partial<FormData>) =>
    setFormData(prev => ({ ...prev, ...patch }))

  const avatarSelection: AgentAvatarSelection = {
    avatarType: formData.avatarType,
    avatarValue: formData.avatarValue,
    avatarUrl: formData.avatarUrl,
    avatarPreviewUrl: formData.avatarPreviewUrl,
    avatarFile,
  }

  const setAvatarSelection = (selection: AgentAvatarSelection) => {
    setFormData(prev => ({
      ...prev,
      avatarType: selection.avatarType,
      avatarValue: selection.avatarValue,
      avatarUrl: selection.avatarUrl,
      avatarPreviewUrl: selection.avatarPreviewUrl,
    }))
    setAvatarFile(selection.avatarFile ?? null)
  }

  const avatarDisplay = getAvatarDisplayProps(avatarSelection)

  const syncAgentAvatar = async (agentId: string) => {
    if (avatarFile) {
      const updated = await agentsApi.uploadAvatar(agentId, avatarFile)
      setFormData(prev => ({
        ...prev,
        avatarType: updated.avatar_type ?? 'image',
        avatarUrl: updated.avatar_url ?? null,
        avatarPreviewUrl: updated.avatar_url ?? null,
        avatarValue: updated.avatar_value ?? '',
      }))
      setAvatarFile(null)
      return
    }
    const avatarPayload = buildAvatarApiPayload(avatarSelection)
    if (Object.keys(avatarPayload).length > 0) {
      await agentsApi.update(agentId, avatarPayload)
    }
  }

  const isRawDbTool = (tool: (typeof allTools)[number]) =>
    tool.type === 'db_query' || tool.type === 'db' || (tool.name && tool.name.startsWith('query_'))

  const mongoReadTool = allTools.find(t => t.name === 'query_mongo_read')
  const sqlReadTool = allTools.find(t => t.name === 'query_sql_read')
  const mongoWriteTool = allTools.find(t => t.name === 'query_mongo_write')
  const sqlWriteTool = allTools.find(t => t.name === 'query_sql_write')

  const activeReadToolId = [mongoReadTool?.id, sqlReadTool?.id].find(id => id && formData.toolIds.includes(id))
  const activeWriteToolId = [mongoWriteTool?.id, sqlWriteTool?.id].find(id => id && formData.toolIds.includes(id))

  const isReadDbChecked = Boolean(activeReadToolId) || formData.toolIds.includes('virtual_db_read')
  const isWriteDbChecked = Boolean(activeWriteToolId) || formData.toolIds.includes('virtual_db_write')

  const readDbConnId = activeReadToolId ? formData.toolDbConnectionIds[activeReadToolId] : (formData.toolDbConnectionIds['virtual_db_read'] || '')
  const writeDbConnId = activeWriteToolId ? formData.toolDbConnectionIds[activeWriteToolId] : (formData.toolDbConnectionIds['virtual_db_write'] || '')

  const handleToggleVirtualDbTool = (mode: 'read' | 'write', currentSelected: boolean) => {
    const virtualId = mode === 'read' ? 'virtual_db_read' : 'virtual_db_write'
    const oldReadIds = [mongoReadTool?.id, sqlReadTool?.id].filter(Boolean) as string[]
    const oldWriteIds = [mongoWriteTool?.id, sqlWriteTool?.id].filter(Boolean) as string[]
    const idsToRemove = mode === 'read' ? [...oldReadIds, virtualId] : [...oldWriteIds, virtualId]

    setFormData(prev => {
      if (currentSelected) {
        const cleanToolIds = prev.toolIds.filter(id => !idsToRemove.includes(id))
        const cleanConnIds = { ...prev.toolDbConnectionIds }
        idsToRemove.forEach(id => delete cleanConnIds[id])
        return { ...prev, toolIds: cleanToolIds, toolDbConnectionIds: cleanConnIds }
      } else {
        return {
          ...prev,
          toolIds: Array.from(new Set([...prev.toolIds, virtualId])),
        }
      }
    })
  }

  const handleSelectDbConnectionForMode = (mode: 'read' | 'write', dbConnId: string) => {
    const conn = dbConnections.find(c => c.id === dbConnId)
    if (!conn) return
    const connType = (conn.connection_type || '').toLowerCase()
    const isMongo = connType.includes('mongo') || (conn.connection_string || '').startsWith('mongodb')

    const targetTool = mode === 'read'
      ? (isMongo ? mongoReadTool : sqlReadTool)
      : (isMongo ? mongoWriteTool : sqlWriteTool)

    const virtualId = mode === 'read' ? 'virtual_db_read' : 'virtual_db_write'
    const oldReadIds = [mongoReadTool?.id, sqlReadTool?.id].filter(Boolean) as string[]
    const oldWriteIds = [mongoWriteTool?.id, sqlWriteTool?.id].filter(Boolean) as string[]
    const idsToRemove = mode === 'read' ? [...oldReadIds, virtualId] : [...oldWriteIds, virtualId]

    setFormData(prev => {
      const cleanToolIds = prev.toolIds.filter(id => !idsToRemove.includes(id))
      const nextToolIds = targetTool?.id ? [...cleanToolIds, targetTool.id] : cleanToolIds
      const cleanConnIds = { ...prev.toolDbConnectionIds }
      idsToRemove.forEach(id => delete cleanConnIds[id])
      if (targetTool?.id) {
        cleanConnIds[targetTool.id] = dbConnId
      }
      return {
        ...prev,
        toolIds: nextToolIds,
        toolDbConnectionIds: cleanConnIds,
      }
    })
  }

  const virtualTools = [
    {
      id: 'virtual_db_read',
      name: 'Read from database',
      description: 'Execute read-only queries against an organization database.',
      mode: 'read' as const,
      isChecked: isReadDbChecked,
      connId: readDbConnId,
    },
    {
      id: 'virtual_db_write',
      name: 'Write to database',
      description: 'Execute write queries against an organization database.',
      mode: 'write' as const,
      isChecked: isWriteDbChecked,
      connId: writeDbConnId,
    },
  ]

  const nonDbTools = allTools.filter(t => t.is_active && !isRawDbTool(t))

  const filteredStandardTools = nonDbTools.filter(t =>
    `${t.name} ${t.description ?? ''} ${t.type}`.toLowerCase().includes(toolSearch.toLowerCase())
  )

  const filteredVirtualTools = virtualTools.filter(vt =>
    `${vt.name} ${vt.description}`.toLowerCase().includes(toolSearch.toLowerCase())
  )

  const selectedTools = allTools.filter(t => selectedToolIds.has(t.id!))
  const isDbQueryTool = isRawDbTool
  const selectedDbQueryTools = selectedTools.filter(isDbQueryTool)

  const currentOrganizationId = () =>
    selectedOrganizationId

  const registryToolDescription = (tool: (typeof allTools)[number]) => {
    const description = tool.description?.trim()
    if (description && description.length >= 10) return description
    return `${tool.name} tool for this agent`
  }

  const syncSelectedTools = async () => {
    if (!createdAgentId) return []

    const organizationId = currentOrganizationId()
    const nextToolRecords = { ...toolRecordIdsByRegistryId }
    const nextAttachedToolIds: string[] = []

    for (const tool of selectedTools) {
      if (!tool.id) continue

      let toolRecordId = nextToolRecords[tool.id]
      const dbConnId = isDbQueryTool(tool) ? formData.toolDbConnectionIds[tool.id] : undefined
      if (!toolRecordId) {
        const created = await toolsApi.create({
          organization_id: organizationId,
          agent_id: createdAgentId,
          tool_id: tool.id,
          user_description: registryToolDescription(tool),
          name: tool.name,
          db_conn_id: dbConnId,
          enabled: toolPermissions[tool.id] !== undefined ? toolPermissions[tool.id] : tool.name !== 'query_db_write',
        })
        toolRecordId = created.id!
        nextToolRecords[tool.id] = toolRecordId
      } else if (isDbQueryTool(tool)) {
        await toolsApi.update(toolRecordId, { db_conn_id: dbConnId })
      }

      nextAttachedToolIds.push(toolRecordId)
    }

    setToolRecordIdsByRegistryId(nextToolRecords)
    setAttachedToolIds(nextAttachedToolIds)

    const permissionsPatch: Record<string, boolean> = {}
    for (const tool of selectedTools) {
      if (tool.name) {
        permissionsPatch[tool.name] = isAskHumanTool(tool)
          ? true
          : (toolPermissions[tool.id!] !== undefined
            ? toolPermissions[tool.id!]
            : tool.name !== 'query_db_write')
      }
    }
    if (Object.keys(permissionsPatch).length > 0) {
      await agentsApi.patchPermissions(createdAgentId, { tools: permissionsPatch })
    }

    return nextAttachedToolIds
  }


  const validateStep = () => {
    const nextErrors: Record<string, string> = {}
    if (step === 0 && formData.name.trim().length < 2) {
      nextErrors.name = 'Name must be at least 2 characters'
    }
    if (step === 0 && canChooseVisibility && formData.ownerScope === 'selected_users' && formData.allowedUserIds.length === 0) {
      nextErrors.allowedUserIds = 'Select at least one user'
    }
    if (step === 3 && formData.prompt.trim().length < 10) {
      nextErrors.prompt = 'System prompt must be at least 10 characters'
    }
    if (step === 3 && formData.guardrails.trim().length < 10) {
      nextErrors.guardrails = 'Guardrails must be at least 10 characters'
    }
    if (step === 1) {
      for (const tool of selectedDbQueryTools) {
        if (tool.id && !formData.toolDbConnectionIds[tool.id]) {
          nextErrors[`dbConn:${tool.id}`] = 'Select a database connection'
        }
      }
    }
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const toggleTool = (toolId: string, selected: boolean) => {
    const tool = allTools.find(t => t.id === toolId)
    if (tool && isAskHumanTool(tool)) return

    setFormData(prev => {
      if (!selected) {
        return { ...prev, toolIds: [...prev.toolIds, toolId] }
      }
      const { [toolId]: _removed, ...toolDbConnectionIds } = prev.toolDbConnectionIds
      return {
        ...prev,
        toolIds: prev.toolIds.filter(id => id !== toolId),
        toolDbConnectionIds,
      }
    })
    setErrors(prev => {
      const { [`dbConn:${toolId}`]: _removed, ...rest } = prev
      return rest
    })
  }

  const selectToolDbConnection = (toolId: string, dbConnId: string) => {
    setFormData(prev => ({
      ...prev,
      toolDbConnectionIds: { ...prev.toolDbConnectionIds, [toolId]: dbConnId },
    }))
    setErrors(prev => {
      const { [`dbConn:${toolId}`]: _removed, ...rest } = prev
      return rest
    })
  }

  const handleNext = async () => {
    if (!validateStep()) return

    const basePayload = {
      organization_id: currentOrganizationId(),
      name: formData.name,
      description: formData.description || undefined,
      prompt: formData.prompt,
      guardrails: formData.guardrails,
      tool_ids: attachedToolIds,
      owner_scope: effectiveOwnerScope,
      allowed_user_ids: effectiveOwnerScope === 'selected_users' ? formData.allowedUserIds : undefined,
      ...buildAvatarApiPayload(avatarSelection),
    }

    if (step === 0) {
      setLoading(true)
      try {
        if (createdAgentId) {
          await agentsApi.update(createdAgentId, basePayload as any)
          await syncAgentAvatar(createdAgentId)
        } else {
          const created = await agentsApi.create(basePayload as any)
          setCreatedAgentId(created.id!)
          await syncAgentAvatar(created.id!)
        }
        setStep(s => Math.min(s + 1, STEPS.length - 1))
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to save agent')
      } finally {
        setLoading(false)
      }
      return
    }

    if (step === 1 && createdAgentId) {
      setLoading(true)
      try {
        const toolIds = await syncSelectedTools()
        await agentsApi.update(createdAgentId, { ...basePayload, tool_ids: toolIds } as any)
        setStep(s => Math.min(s + 1, STEPS.length - 1))
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to save tools')
      } finally {
        setLoading(false)
      }
      return
    }

    if (step === 2) {
      setStep(s => Math.min(s + 1, STEPS.length - 1))
      return
    }

    if (step === 3 && createdAgentId) {
      setLoading(true)
      try {
        await agentsApi.update(createdAgentId, {
          organization_id: currentOrganizationId(),
          name: formData.name,
          description: formData.description || undefined,
          prompt: formData.prompt,
          guardrails: formData.guardrails,
          tool_ids: attachedToolIds,
        } as any)
        setStep(s => Math.min(s + 1, STEPS.length - 1))
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to save prompt')
      } finally {
        setLoading(false)
      }
      return
    }

    setStep(s => Math.min(s + 1, STEPS.length - 1))
  }

  const handleDeploy = async () => {
    if (!createdAgentId) {
      toast.error('Agent was not created yet')
      return
    }

    const payload = {
      organization_id: currentOrganizationId(),
      name: formData.name,
      description: formData.description || undefined,
      prompt: formData.prompt,
      guardrails: formData.guardrails,
      tool_ids: attachedToolIds,
    }

    setLoading(true)
    try {
      await agentsApi.update(createdAgentId, payload as any)
      toast.success('Agent deployed successfully')
      router.push('/admin/agents')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to deploy agent')
    } finally {
      setLoading(false)
    }
  }

  const handleGeneratePrompt = async () => {
    if (!formData.name.trim()) {
      toast.error('Add an agent name in Step 1 first')
      return
    }
    setIsGeneratingPrompt(true)
    try {
      const res = await promptGeneratorApi.generate(
        formData.name,
        formData.description || `An AI agent named ${formData.name}`
      )
      update({
        prompt: res.prompt,
        guardrails: res.guardrails || formData.guardrails,
      })
      toast.success('Prompt and guardrails generated with AI!')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate prompt')
    } finally {
      setIsGeneratingPrompt(false)
    }
  }

  const filteredTools = allTools.filter(t =>
    t.is_active &&
    `${t.name} ${t.description ?? ''} ${t.type}`.toLowerCase().includes(toolSearch.toLowerCase())
  )

  return (
    <>
      <PageHeader
        title="Create Agent"
        description="Configure and deploy a new AI agent"
        actions={
          <Link href="/admin/agents">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Agents
            </Button>
          </Link>
        }
      />

      <div className="mb-8">
        <Stepper steps={STEPS} currentStep={step} />
      </div>

      {step === 0 && (
        <div className="animate-fadeIn grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass p-6 rounded-[var(--radius-lg)] space-y-4">
            {isSuperAdmin && (
              <FormField label="Organization">
                <Select
                  value={formData.organization_id}
                  onValueChange={v => update({ organization_id: v })}
                  options={orgs.map(org => ({ value: org.id!, label: org.name }))}
                />
              </FormField>
            )}
            {canChooseVisibility && (
              <FormField label="Visibility">
                <Select
                  value={formData.ownerScope}
                  onValueChange={v => update({ ownerScope: v as 'user' | 'organization' | 'selected_users' })}
                  options={[
                    { value: 'organization', label: 'Organization — visible to everyone in the org' },
                    { value: 'selected_users', label: 'Selected users — visible to specific people only' },
                    { value: 'user', label: 'Personal — only visible to you' },
                  ]}
                />
              </FormField>
            )}
            {canChooseVisibility && formData.ownerScope === 'selected_users' && (
              <FormField
                label={`Visible to (${formData.allowedUserIds.length} selected)`}
                error={errors.allowedUserIds}
              >
                <SearchInput
                  value={userSearch}
                  onChange={e => setUserSearch(e.target.value)}
                  placeholder="Search users..."
                  className="mb-2"
                />
                <div className="max-h-48 overflow-y-auto space-y-1 border border-[var(--border)] rounded-[var(--radius-md)] p-2">
                  {filteredOrgUsers.length === 0 ? (
                    <p className="text-[12px] text-[var(--text-3)] p-2">No other users found in this organization.</p>
                  ) : (
                    filteredOrgUsers.map(u => {
                      const selected = formData.allowedUserIds.includes(u.id!)
                      return (
                        <label key={u.id} className="flex items-center gap-2 p-2 rounded-[var(--radius-sm)] cursor-pointer hover:bg-[var(--surface-2)]">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => update({
                              allowedUserIds: selected
                                ? formData.allowedUserIds.filter(id => id !== u.id)
                                : [...formData.allowedUserIds, u.id!],
                            })}
                            className="w-4 h-4 accent-violet-600"
                          />
                          <span className="text-[13px]">{u.name}</span>
                          <span className="text-[12px] text-[var(--text-3)]">{u.email}</span>
                        </label>
                      )
                    })
                  )}
                </div>
              </FormField>
            )}
            <FormField label="Name" error={errors.name}>
              <Input
                value={formData.name}
                onChange={e => update({ name: e.target.value })}
                placeholder="My Agent"
              />
            </FormField>
            <FormField label="Description">
              <Textarea
                value={formData.description}
                onChange={e => update({ description: e.target.value })}
                placeholder="What does this agent do?"
              />
            </FormField>
            <AgentAvatarPicker
              name={formData.name}
              value={avatarSelection}
              onChange={setAvatarSelection}
            />
          </div>
          <div className="glass p-6 rounded-[var(--radius-lg)]">
            <p className="text-[12px] text-[var(--text-3)] mb-4">Live preview</p>
            <div className="flex items-start gap-4">
              <AgentAvatar
                name={formData.name || 'Untitled Agent'}
                avatarType={avatarDisplay.avatarType}
                avatarValue={avatarDisplay.avatarValue}
                avatarUrl={avatarDisplay.avatarUrl}
                size="md"
                shape={avatarDisplay.shape}
              />
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-[16px] font-semibold">
                    {formData.name || 'Untitled Agent'}
                  </h3>
                  <Badge variant="neutral">Draft</Badge>
                </div>
                <p className="text-[13px] text-[var(--text-3)] mt-1">
                  {formData.description || 'No description yet'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="animate-fadeIn space-y-6">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] font-medium text-[var(--text-2)]">System Prompt</span>
              <button
                type="button"
                onClick={handleGeneratePrompt}
                disabled={isGeneratingPrompt || !formData.name.trim()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-md)] text-[12px] font-medium bg-violet-600 text-white hover:bg-violet-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                title={!formData.name.trim() ? 'Set an agent name in Step 1 first' : 'Generate prompt using AI'}
              >
                {isGeneratingPrompt ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                {isGeneratingPrompt ? 'Generating…' : 'Generate with AI'}
              </button>
            </div>
            <CodeEditor
              value={formData.prompt}
              onChange={val => update({ prompt: val })}
              charLimit={4000}
              error={errors.prompt}
              placeholder="You are a helpful AI assistant..."
            />
          </div>
          <div>
            <p className="text-[13px] font-medium mb-3">Prompt templates</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {PROMPT_TEMPLATES.map(template => (
                <button
                  key={template.title}
                  type="button"
                  onClick={() => update({ prompt: template.prompt })}
                  className="glass glass-hover p-4 rounded-[var(--radius-lg)] text-left"
                >
                  <p className="text-[14px] font-medium">{template.title}</p>
                  <p className="text-[12px] text-[var(--text-3)] mt-1 line-clamp-2">
                    {template.prompt}
                  </p>
                </button>
              ))}
            </div>
          </div>
          <div className="glass p-5 rounded-[var(--radius-lg)] space-y-3">
            <FormField label="Guardrails" error={errors.guardrails}>
              <InfoBox variant="info">
                Guardrails define safety rules enforced on every agent invocation.
              </InfoBox>
              <Textarea
                value={formData.guardrails}
                onChange={e => update({ guardrails: e.target.value })}
                placeholder="Never share PII. Refuse harmful requests..."
                className={errors.guardrails ? 'border-red-400 focus-visible:ring-red-400' : ''}
              />
            </FormField>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="animate-fadeIn grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <SearchInput
              value={toolSearch}
              onChange={e => setToolSearch(e.target.value)}
              placeholder="Search tools..."
            />
            <div className="space-y-2">
              {/* Virtual Database Tools */}
              {filteredVirtualTools.map(vt => (
                <label key={vt.id} className="glass flex items-start gap-3 p-4 rounded-[var(--radius-lg)] cursor-pointer hover:border-violet-500/30">
                  <input
                    type="checkbox"
                    checked={vt.isChecked}
                    onChange={() => handleToggleVirtualDbTool(vt.mode, vt.isChecked)}
                    className="mt-1 w-4 h-4 accent-violet-600"
                  />
                  <Database className="w-4 h-4 text-violet-600 dark:text-violet-400 mt-0.5" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-medium">{vt.name}</span>
                    </div>
                    <p className="text-[12px] text-[var(--text-3)] mt-1">{vt.description}</p>

                    {vt.isChecked && (
                      <div className="mt-3 max-w-md" onClick={e => e.stopPropagation()}>
                        <FormField
                          label="Database connection"
                          error={errors[`dbConn:${vt.mode === 'read' ? activeReadToolId : activeWriteToolId}`]}
                        >
                          <Select
                            value={vt.connId}
                            onValueChange={value => handleSelectDbConnectionForMode(vt.mode, value)}
                            options={dbConnections.map(conn => ({
                              value: conn.id!,
                              label: dbConnectionLabel(conn),
                            }))}
                            placeholder={dbConnectionsLoading ? 'Loading connections...' : 'Select database connection'}
                            disabled={dbConnectionsLoading || dbConnections.length === 0}
                            required
                          />
                        </FormField>
                        {dbConnections.length === 0 && !dbConnectionsLoading && (
                          <p className="text-[12px] text-[var(--text-3)] mt-1">
                            No database connections available for this organization.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </label>
              ))}

              {/* Standard Non-DB Tools */}
              {filteredStandardTools.map(tool => {
                const selected = selectedToolIds.has(tool.id!)
                const isLocked = isAskHumanTool(tool)
                return (
                  <label
                    key={tool.id}
                    className="glass flex items-start gap-3 p-4 rounded-[var(--radius-lg)] cursor-pointer hover:border-violet-500/30"
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleTool(tool.id!, selected)}
                      disabled={isLocked}
                      className="mt-1 w-4 h-4 accent-violet-600"
                    />
                    <Wrench className="w-4 h-4 text-violet-600 dark:text-violet-400 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[14px] font-medium">{formatToolName(tool.name)}</span>
                      </div>
                      <p className="text-[12px] text-[var(--text-3)] mt-1">{tool.description}</p>
                    </div>
                  </label>
                )
              })}
            </div>
            <Link href="/admin/tools/create" target="_blank">
              <Button variant="ghost" size="sm">
                Create new tool +
              </Button>
            </Link>
          </div>
          <div className="glass p-5 rounded-[var(--radius-lg)] h-fit sticky top-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-[14px] font-medium">Selected Tools</span>
              <Badge variant="primary">{selectedTools.length}</Badge>
            </div>
            {selectedTools.length === 0 ? (
              <div className="border border-dashed border-[var(--border-2)] rounded-lg p-6 text-center text-[13px] text-[var(--text-3)]">
                No tools selected
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {selectedTools.map(tool => (
                  <span
                    key={tool.id}
                    className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300 rounded-full px-2.5 py-1 text-[12px]"
                  >
                    {isDbQueryTool(tool) && <Database className="w-3 h-3" />}
                    {formatToolName(tool.name)}
                    {!isAskHumanTool(tool) && (
                      <button
                        type="button"
                        onClick={() => tool.id && toggleTool(tool.id, true)}
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {step === 2 && createdAgentId && (
        <div className="animate-fadeIn">
          <AgentMcpStep agentId={createdAgentId} />
        </div>
      )}

      {step === 4 && (
        <div className="animate-fadeIn space-y-5">
          <div className="glass border border-violet-500/20 p-4 rounded-[var(--radius-lg)] flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            <span className="text-[14px] font-medium">Ready to deploy</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Identity</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(0)}>Edit</Button>
              </div>
              <p className="text-[14px]">{formData.name}</p>
              <p className="text-[12px] text-[var(--text-3)] mt-1">{formData.description || '—'}</p>
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Prompt</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(3)}>Edit</Button>
              </div>
              <p className="text-[12px] font-mono text-[var(--text-3)] line-clamp-4">
                {formData.prompt}
              </p>
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)] lg:col-span-2">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Tools ({selectedTools.length})</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(1)}>Edit</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedTools.length === 0 ? (
                  <span className="text-[13px] text-[var(--text-3)]">No tools attached</span>
                ) : (
                  selectedTools.map(t => (
                    <Badge key={t.id} variant="neutral">{formatToolName(t.name)}</Badge>
                  ))
                )}
              </div>
            </div>
          </div>
          <Button
            variant="primary"
            size="lg"
            className="w-full"
            onClick={handleDeploy}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Rocket className="w-4 h-4 mr-2" />
            )}
            Deploy Agent
          </Button>
        </div>
      )}

      {step < 4 && (
        <div className="flex justify-between mt-8">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setStep(s => Math.max(s - 1, 0))}
            disabled={step === 0}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <Button variant="primary" size="sm" onClick={handleNext} disabled={loading}>
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <>
                Next
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </div>
      )}
    </>
  )
}


