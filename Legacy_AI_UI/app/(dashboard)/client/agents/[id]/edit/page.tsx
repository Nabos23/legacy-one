'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, ArrowRight, CheckCircle2, Database, Loader2, Plug2, Save, Sparkles, Wrench, X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { Stepper } from '@/components/ui/stepper'
import { CodeEditor } from '@/components/ui/code-editor'
import { Badge } from '@/components/ui/badge'
import { InfoBox } from '@/components/ui/info-box'
import { FormField } from '@/components/ui/form-field'
import { AgentMcpStep } from '@/components/mcp/agent-mcp-step'
import { useToast } from '@/hooks/use-toast'
import { useToolRegistry } from '@/hooks/use-tool-registry'
import { useDbConnections } from '@/hooks/use-db-connections'
import { useAgentPermissions } from '@/hooks/use-agent-permissions'
import type { ToolPublic, ToolRegistryPublic, ConnectorPermissions } from '@/types'
import { useConnectors } from '@/hooks/use-connectors'
import { useConnectorStatuses } from '@/hooks/use-connector-statuses'
import { useMcpServersByAgent } from '@/hooks/use-mcp-servers'
import { useUsers } from '@/hooks/use-users'
import { useAuth } from '@/contexts/auth-context'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import { agentsApi, promptGeneratorApi, toolsApi } from '@/lib/api'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import { AgentAvatarPicker, buildAvatarApiPayload, getAvatarDisplayProps, normalizeAvatarSelection, type AgentAvatarSelection } from '@/components/dashboard/agent-avatar-picker'
import { DEFAULT_AGENT_STICKER_ID } from '@/lib/agent-stickers'
import { agentVisibilityLabel, formatToolName } from '@/lib/utils'
import type { AgentAvatarType } from '@/types'

const STEPS = ['Identity', 'Tools', 'Connectors', 'MCP Servers', 'Prompt & Guardrails', 'Review']

interface ToolCredentialFields {
  api_key: string
  base_url: string
  model: string
}

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
  toolCredentials: Record<string, ToolCredentialFields>
  connectorIds: string[]
  ownerScope: 'user' | 'organization' | 'selected_users' | 'team'
  allowedUserIds: string[]
}

export default function EditAgentPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()
  const { user } = useAuth()
  const isSuperAdmin = user?.role === 'super_admin' || user?.role === 'super admin'
  const isOrgAdmin = user?.role === 'org_admin' || user?.role === 'org admin' || user?.role === 'admin'
  const isOrgManager = user?.role === 'org_manager' || user?.role === 'org manager'
  const canChooseVisibility = isSuperAdmin || isOrgAdmin || isOrgManager
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [uploadingAvatar, setUploadingAvatar] = useState(false)
  const [generatingPrompt, setGeneratingPrompt] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const [toolSearch, setToolSearch] = useState('')
  const [connectorSearch, setConnectorSearch] = useState('')
  const [userSearch, setUserSearch] = useState('')
  const [toolCache, setToolCache] = useState<Record<string, ToolRegistryPublic>>({})
  const [pageSize, setPageSize] = useState(100)
  const [page, setPage] = useState(1)
  const [organizationId, setOrganizationId] = useState('')
  const { data: toolsData, loading: toolsLoading } = useToolRegistry(page, pageSize, { isActive: true, sortBy: 'name', sortOrder: 'asc' })
  const allTools = toolsData?.items ?? []
  const { data: allConnectors } = useConnectors()
  const { statuses: connectorStatuses } = useConnectorStatuses(allConnectors.map(c => c.id))
  const { data: mcpServers } = useMcpServersByAgent(id)
  const { data: orgUsersData } = useUsers(1, organizationId || undefined, undefined, undefined, 100, {}, canChooseVisibility)
  const orgUsers = (orgUsersData?.items ?? []).filter(u => u.id !== user?.id)
  const filteredOrgUsers = orgUsers.filter(u =>
    `${u.name} ${u.email}`.toLowerCase().includes(userSearch.toLowerCase())
  )
  const { connectorsPermissions, setConnectorsPermissions, updatePermissions } = useAgentPermissions(id)
  const [toolRecordIdsByRegistryId, setToolRecordIdsByRegistryId] = useState<Record<string, string>>({})
  const [hasCustomCredentialsMap, setHasCustomCredentialsMap] = useState<Record<string, boolean>>({})
  const [formData, setFormData] = useState<FormData>({
    name: '', description: '', avatarType: 'sticker', avatarValue: DEFAULT_AGENT_STICKER_ID, avatarUrl: null, avatarPreviewUrl: null,
    prompt: '', guardrails: '', toolIds: [], toolDbConnectionIds: {}, toolCredentials: {}, connectorIds: [], ownerScope: 'organization', allowedUserIds: [],
  })
  useBreadcrumbLabel(id, formData.name)

  const canGeneratePrompt = (formData?.name ?? '').trim().length >= 2

  const handleGeneratePrompt = async () => {
    if (!id || !canGeneratePrompt) return
    setGeneratingPrompt(true)
    try {
      const res = await promptGeneratorApi.generateForAgent(id as string)
      update({
        prompt: res.prompt,
        guardrails: res.guardrails || formData.guardrails,
      })
      toast.success('Prompt and guardrails generated with AI!')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate prompt')
    } finally {
      setGeneratingPrompt(false)
    }
  }

  const isGenerateImageTool = (tool: ToolRegistryPublic) => {
    const key = `${tool.id ?? ''} ${tool.name ?? ''}`.toLowerCase().replace(/[\s-]+/g, '_')
    return key.includes('generate_image')
  }



  const updateToolCredential = (
    toolId: string,
    field: keyof ToolCredentialFields,
    value: string,
  ) => {
    setFormData(prev => ({
      ...prev,
      toolCredentials: {
        ...prev.toolCredentials,
        [toolId]: {
          api_key: prev.toolCredentials[toolId]?.api_key ?? '',
          base_url: prev.toolCredentials[toolId]?.base_url ?? '',
          model: prev.toolCredentials[toolId]?.model ?? '',
          [field]: value,
        },
      },
    }))
  }

  useEffect(() => {
    agentsApi.get(id)
      .then(async agent => {
        const normalized = normalizeAvatarSelection({
          avatarType: agent.avatar_type,
          avatarValue: agent.avatar_value ?? undefined,
          avatarUrl: agent.avatar_url,
        })
        
        const attachedInstances = await Promise.all(
          (agent.tool_ids ?? []).map(tId =>
            toolsApi.get(tId).catch(() => null)
          )
        )
        const validInstances = attachedInstances.filter(Boolean)
        const recordIdsMap: Record<string, string> = {}
        const credentialsMap: Record<string, ToolCredentialFields> = {}
        const registryToolIds: string[] = []

        setToolCache(prev => {
          const next = { ...prev }
          for (const inst of validInstances) {
            if (inst && inst.tool_id) {
              next[inst.tool_id] = {
                id: inst.tool_id,
                name: inst.name ?? '',
                description: inst.user_description ?? '',
                type: 'unknown',
                is_active: true,
                created_at: inst.created_at,
              }
            }
          }
          return next
        })

        const customCredsMap: Record<string, boolean> = {}
        const dbConnIdsMap: Record<string, string> = {}
        for (const inst of validInstances) {
          if (inst && inst.tool_id) {
            recordIdsMap[inst.tool_id] = inst.id!
            registryToolIds.push(inst.tool_id)
            if ((inst as any).db_conn_id) {
              dbConnIdsMap[inst.tool_id] = (inst as any).db_conn_id
            }
            if ((inst as any).credentials) {
              credentialsMap[inst.tool_id] = (inst as any).credentials as any
            }
            if ((inst as any).has_custom_credentials) {
              customCredsMap[inst.tool_id] = true
            }
          }
        }

        setHasCustomCredentialsMap(customCredsMap)
        setToolRecordIdsByRegistryId(recordIdsMap)
        setOrganizationId(agent.organization_id)
        setFormData({
          name: agent.name ?? '',
          description: agent.description || agent.user_description || '',
          avatarType: normalized.avatarType,
          avatarValue: normalized.avatarValue,
          avatarUrl: normalized.avatarUrl,
          avatarPreviewUrl: normalized.avatarPreviewUrl,
          prompt: agent.prompt || agent.instructions || '',
          guardrails: agent.guardrails ?? '',
          toolIds: registryToolIds,
          toolDbConnectionIds: dbConnIdsMap,
          toolCredentials: credentialsMap,
          connectorIds: agent.connector_ids ?? [],
          ownerScope: agent.owner_scope ?? 'organization',
          allowedUserIds: agent.allowed_user_ids ?? [],
        })
      })
      .catch(() => toast.error('Failed to load agent'))
      .finally(() => setFetching(false))
  }, [id])

  const selectedOrganizationId = organizationId || user?.organization_id || ''
  const { data: dbConnectionsData, loading: dbConnectionsLoading } = useDbConnections(1, selectedOrganizationId || undefined, 100)
  const dbConnections = (dbConnectionsData?.items ?? []).filter(conn => !selectedOrganizationId || conn.organization_id === selectedOrganizationId)
  const dbConnectionLabel = (conn: (typeof dbConnections)[number]) =>
    conn.name?.trim() || conn.connection_string

  const isRawDbTool = (tool: ToolRegistryPublic) =>
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

  useEffect(() => {
    if (toolsData?.items) {
      setToolCache(prev => {
        const next = { ...prev }
        for (const tool of toolsData.items) {
          if (tool.id) next[tool.id] = tool
        }
        return next
      })
    }
  }, [toolsData])

  const isAskHumanTool = (tool: ToolRegistryPublic) => {
    const key = `${tool.id ?? ''} ${tool.name ?? ''}`.toLowerCase().replace(/[\s-]+/g, '_')
    return key.includes('ask_human') || key.includes('human_in_loop')
  }

  useEffect(() => {
    const askHumanToolIds = allTools.filter(isAskHumanTool).map(tool => tool.id!).filter(Boolean)
    if (askHumanToolIds.length === 0) return

    setFormData(prev => {
      const nextToolIds = Array.from(new Set([...prev.toolIds, ...askHumanToolIds]))
      return nextToolIds.length === prev.toolIds.length ? prev : { ...prev, toolIds: nextToolIds }
    })
  }, [allTools])

  const update = (patch: Partial<FormData>) => setFormData(prev => ({ ...prev, ...patch }))

  const avatarSelection: AgentAvatarSelection = {
    avatarType: formData.avatarType,
    avatarValue: formData.avatarValue,
    avatarUrl: formData.avatarUrl,
    avatarPreviewUrl: formData.avatarPreviewUrl,
  }

  const setAvatarSelection = (selection: AgentAvatarSelection) => {
    setFormData(prev => ({
      ...prev,
      avatarType: selection.avatarType,
      avatarValue: selection.avatarValue,
      avatarUrl: selection.avatarUrl,
      avatarPreviewUrl: selection.avatarPreviewUrl,
    }))
  }

  const avatarDisplay = getAvatarDisplayProps(avatarSelection)

  const handleAvatarUpload = async (file: File) => {
    setUploadingAvatar(true)
    try {
      const updated = await agentsApi.uploadAvatar(id, file)
      setFormData(prev => ({
        ...prev,
        avatarType: updated.avatar_type ?? 'image',
        avatarValue: updated.avatar_value ?? '',
        avatarUrl: updated.avatar_url ?? null,
        avatarPreviewUrl: updated.avatar_url ?? null,
      }))
      return updated.avatar_url ?? null
    } finally {
      setUploadingAvatar(false)
    }
  }

  const validateStep = () => {
    const errs: Record<string, string> = {}
    if (step === 0 && formData.name.trim().length < 2) errs.name = 'Name must be at least 2 characters'
    if (step === 0 && canChooseVisibility && formData.ownerScope === 'selected_users' && formData.allowedUserIds.length === 0) {
      errs.allowedUserIds = 'Select at least one user'
    }
    if (step === 4 && formData.prompt.trim().length < 10) errs.prompt = 'System prompt must be at least 10 characters'
    if (step === 4 && formData.guardrails.trim().length < 10) errs.guardrails = 'Guardrails must be at least 10 characters'
    if (step === 2) {
      for (const cid of formData.connectorIds) {
        const conn = allConnectors.find(c => c.id === cid)
        if (conn) {
          const categories = conn.permissions ? Object.keys(conn.permissions) : ['read', 'write', 'delete']
          const userPerms = connectorsPermissions[conn.provider_id]
          const isAnyChecked = categories.some(cat => userPerms?.[cat] !== undefined ? userPerms[cat] : true)
          if (!isAnyChecked) {
            toast.error(`At least one permission must be granted for connector '${conn.name}'.`)
            return false
          }
        }
      }
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const buildToolCredentialsPayload = (tool: ToolRegistryPublic) => {
    if (!tool.id || !isGenerateImageTool(tool)) return undefined
    const creds = formData.toolCredentials[tool.id]
    if (!creds || (!creds.api_key && !creds.base_url && !creds.model)) return undefined
    return {
      api_key: creds.api_key || undefined,
      base_url: creds.base_url || undefined,
      model: creds.model || undefined,
    }
  }

  const syncSelectedTools = async () => {
    const orgId = organizationId || user?.organization_id || ''
    const nextToolRecords = { ...toolRecordIdsByRegistryId }
    const nextAttachedToolIds: string[] = []

    const selectedToolIdsSet = new Set(formData.toolIds)
    for (const [registryId, instanceId] of Object.entries(toolRecordIdsByRegistryId)) {
      if (!selectedToolIdsSet.has(registryId)) {
        await toolsApi.delete(instanceId).catch(() => {})
        delete nextToolRecords[registryId]
      }
    }

    for (const tool of selectedTools) {
      if (!tool.id) continue

      let toolRecordId = nextToolRecords[tool.id]
      const dbConnId = isRawDbTool(tool) ? formData.toolDbConnectionIds[tool.id] : undefined
      const credentials = buildToolCredentialsPayload(tool)

      if (!toolRecordId) {
        const created = await toolsApi.create({
          organization_id: orgId,
          agent_id: id,
          tool_id: tool.id,
          user_description: tool.description || `${tool.name} tool`,
          name: tool.name,
          db_conn_id: dbConnId,
          credentials,
        })
        toolRecordId = created.id!
        nextToolRecords[tool.id] = toolRecordId
      } else {
        const updates: Record<string, unknown> = {}
        if (isRawDbTool(tool)) updates.db_conn_id = dbConnId
        if (credentials) updates.credentials = credentials
        if (Object.keys(updates).length > 0) {
          await toolsApi.update(toolRecordId, updates)
        }
      }

      nextAttachedToolIds.push(toolRecordId)
    }

    setToolRecordIdsByRegistryId(nextToolRecords)

    return nextAttachedToolIds
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

  const filteredTools = filteredStandardTools

  const handleSave = async () => {
    for (const cid of formData.connectorIds) {
      const conn = allConnectors.find(c => c.id === cid)
      if (conn) {
        const categories = conn.permissions ? Object.keys(conn.permissions) : ['read', 'write', 'delete']
        const userPerms = connectorsPermissions[conn.provider_id]
        const isAnyChecked = categories.some(cat => userPerms?.[cat] !== undefined ? userPerms[cat] : true)
        if (!isAnyChecked) {
          toast.error(`At least one permission must be granted for connector '${conn.name}'.`)
          return
        }
      }
    }
    setLoading(true)
    try {
      const syncedToolIds = await syncSelectedTools()
      await agentsApi.update(id, {
        name: formData.name,
        description: formData.description || undefined,
        prompt: formData.prompt,
        guardrails: formData.guardrails,
        tool_ids: syncedToolIds,
        connector_ids: formData.connectorIds,
        allowed_user_ids: canChooseVisibility && formData.ownerScope === 'selected_users' ? formData.allowedUserIds : undefined,
        ...buildAvatarApiPayload(avatarSelection),
      })
      await updatePermissions(undefined, connectorsPermissions)
      toast.success('Agent updated successfully')
      router.push('/client/agents')
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Failed to update agent')
    } finally {
      setLoading(false)
    }
  }

  const selectedTools = formData.toolIds
    .map(id => toolCache[id])
    .filter((tool): tool is ToolRegistryPublic => Boolean(tool))

  const filteredConnectors = allConnectors.filter(c =>
    connectorStatuses[c.id]?.connected &&
    `${c.name} ${c.category} ${c.description}`.toLowerCase().includes(connectorSearch.toLowerCase())
  )
  const selectedConnectors = allConnectors.filter(c => formData.connectorIds.includes(c.id))

  if (fetching) {
    return <div className="flex items-center justify-center h-64 text-[var(--text-3)]">Loading agent…</div>
  }

  return (
    <>
      <PageHeader
        title="Edit Agent"
        description="Update your agent's configuration"
        actions={
          <Link href="/client/agents">
            <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-2" /> Agents</Button>
          </Link>
        }
      />

      <div className="mb-8">
        <Stepper steps={STEPS} currentStep={step} />
      </div>

      {/* Step 0 — Identity */}
      {step === 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass p-6 rounded-[var(--radius-lg)] space-y-4">
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
                                ? formData.allowedUserIds.filter(uid => uid !== u.id)
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
              <Input value={formData.name} onChange={e => update({ name: e.target.value })} />
            </FormField>
            <FormField label="Description">
              <Textarea value={formData.description} onChange={e => update({ description: e.target.value })} />
            </FormField>
            <AgentAvatarPicker
              name={formData.name}
              value={avatarSelection}
              onChange={setAvatarSelection}
              onUpload={handleAvatarUpload}
              uploading={uploadingAvatar}
            />
          </div>
          <div className="glass p-6 rounded-[var(--radius-lg)]">
            <p className="text-[12px] text-[var(--text-3)] mb-4">Preview</p>
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
                  <h3 className="text-[16px] font-semibold">{formData.name || 'Untitled Agent'}</h3>
                  <Badge variant="warning">Editing</Badge>
                  <Badge variant={formData.ownerScope === 'organization' ? 'info' : 'neutral'}>
                    {agentVisibilityLabel({ owner_scope: formData.ownerScope, allowed_user_ids: formData.allowedUserIds })}
                  </Badge>
                </div>
                <p className="text-[13px] text-[var(--text-3)] mt-1">{formData.description || 'No description'}</p>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Step 4 — Prompt & Guardrails */}
      {step === 4 && (
        <div className="space-y-6">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] font-medium">System Prompt</span>
              {canGeneratePrompt && (
                <button
                  type="button"
                  onClick={handleGeneratePrompt}
                  disabled={generatingPrompt}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-md)] text-[12px] font-medium bg-violet-600 hover:bg-violet-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {generatingPrompt ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  {generatingPrompt ? 'Generating…' : 'Generate with AI'}
                </button>
              )}
            </div>
            <CodeEditor value={formData.prompt} onChange={val => update({ prompt: val })} charLimit={4000} error={errors.prompt} placeholder="You are a helpful AI assistant..." />
          </div>
          <div className="glass p-5 rounded-[var(--radius-lg)]">
            <FormField label="Guardrails" error={errors.guardrails}>
              <div className="space-y-3">
                <InfoBox variant="info">Guardrails define safety rules enforced on every invocation.</InfoBox>
                <Textarea
                  value={formData.guardrails}
                  onChange={e => update({ guardrails: e.target.value })}
                  placeholder="Never share PII. Refuse harmful requests…"
                  className={errors.guardrails ? 'border-red-400 focus-visible:ring-red-400' : ''}
                />
              </div>
            </FormField>
          </div>
        </div>
      )}

      {/* Step 1 — Tools */}
      {step === 1 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mt-2">
              <span className="text-[12px] text-[var(--text-3)]">Page {page} of {toolsData?.total_pages ?? 1}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1 || toolsLoading}
                  className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-[13px] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage(p => Math.min(toolsData?.total_pages ?? p, p + 1))}
                  disabled={page >= (toolsData?.total_pages ?? 1) || toolsLoading}
                  className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-[13px] disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
                <select
                  value={pageSize}
                  onChange={e => {
                    const size = Number(e.target.value)
                    setPageSize(size)
                    setPage(1)
                  }}
                  className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[13px]"
                >
                  {[5, 10, 20, 50].map(size => (
                    <option key={size} value={size}>{size} per page</option>
                  ))}
                </select>
              </div>
            </div>
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
                          hint={dbConnections.length === 0 && !dbConnectionsLoading ? 'No database connections available for this organization.' : undefined}
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
                      </div>
                    )}
                  </div>
                </label>
              ))}

              {/* Standard Non-DB Tools */}
              {filteredStandardTools.map(tool => {
                const selected = formData.toolIds.includes(tool.id!)
                const isLocked = isAskHumanTool(tool)
                return (
                  <label key={tool.id} className="glass flex items-start gap-3 p-4 rounded-[var(--radius-lg)] cursor-pointer hover:border-violet-500/30">
                    <input type="checkbox" checked={selected} onChange={() => {
                      if (isLocked) return
                      update({ toolIds: selected ? formData.toolIds.filter(i => i !== tool.id) : [...formData.toolIds, tool.id!] })
                    }} disabled={isLocked} className="mt-1 w-4 h-4 accent-violet-600" />
                    <Wrench className="w-4 h-4 text-violet-600 dark:text-violet-400 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[14px] font-medium">{formatToolName(tool.name ?? tool.description)}</span>
                        <Badge variant="neutral" className="font-mono text-[10px]">{tool.id}</Badge>
                      </div>
                      <p className="text-[12px] text-[var(--text-3)] mt-1">{tool.description}</p>
                    </div>
                  </label>
                )
              })}
            </div>
          </div>
          <div className="glass p-5 rounded-[var(--radius-lg)] h-fit sticky top-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-[14px] font-medium">Selected Tools</span>
              <Badge variant="primary">{selectedTools.length}</Badge>
            </div>
            {selectedTools.length === 0 ? (
              <div className="border border-dashed border-[var(--border-2)] rounded-lg p-6 text-center text-[13px] text-[var(--text-3)]">No tools selected</div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {selectedTools.map(tool => (
                  <span key={tool.id} className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/50 dark:text-violet-300 rounded-full px-2.5 py-1 text-[12px]">
                    {formatToolName(tool.name ?? tool.description)}
                    {!isAskHumanTool(tool) && (
                      <button type="button" onClick={() => update({ toolIds: formData.toolIds.filter(i => i !== tool.id) })}>
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
            )}

            {/* Custom image-model credentials — only shows when generate_image is selected */}
            {selectedTools.filter(isGenerateImageTool).map(tool => (
              <div key={`creds-${tool.id}`} className="mt-4 pt-4 border-t border-[var(--border)] space-y-3">
                <p className="text-[12px] font-medium text-[var(--text-2)]">
                  Custom image model (optional)
                </p>
                <p className="text-[11px] text-[var(--text-3)] -mt-2">
                  Leave blank to use the organization default model.
                </p>
                <FormField label="API key">
                  <Input
                    type="password"
                    value={formData.toolCredentials[tool.id!]?.api_key ?? ''}
                    onChange={e => updateToolCredential(tool.id!, 'api_key', e.target.value)}
                    placeholder={hasCustomCredentialsMap[tool.id!] ? '•••••••• (saved — leave blank to keep)' : 'sk-...'}
                  />
                </FormField>
                <FormField label="Base URL">
                  <Input
                    value={formData.toolCredentials[tool.id!]?.base_url ?? ''}
                    onChange={e => updateToolCredential(tool.id!, 'base_url', e.target.value)}
                    placeholder="https://api.openai.com/v1"
                  />
                </FormField>
                <FormField label="Model">
                  <Input
                    value={formData.toolCredentials[tool.id!]?.model ?? ''}
                    onChange={e => updateToolCredential(tool.id!, 'model', e.target.value)}
                    placeholder="gpt-image-1"
                  />
                </FormField>
                {hasCustomCredentialsMap[tool.id!] && (
                  <p className="text-[11px] text-[var(--text-3)]">
                    A custom API key is already saved for this tool. Fields left blank keep the current saved value.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step 2 — Connectors */}
      {step === 2 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <SearchInput value={connectorSearch} onChange={e => setConnectorSearch(e.target.value)} placeholder="Search connectors…" />
            <div className="space-y-2">
              {filteredConnectors.map(connector => {
                const selected = formData.connectorIds.includes(connector.id)
                return (
                  <label key={connector.id} className="glass flex items-start gap-3 p-4 rounded-[var(--radius-lg)] cursor-pointer hover:border-cyan-500/30">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => update({ connectorIds: selected ? formData.connectorIds.filter(i => i !== connector.id) : [...formData.connectorIds, connector.id] })}
                      className="mt-1 w-4 h-4 accent-cyan-600"
                    />
                    <Plug2 className="w-4 h-4 text-cyan-600 dark:text-cyan-400 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[14px] font-medium">{connector.name}</span>
                        <Badge variant="neutral" className="text-[10px]">{connector.category}</Badge>
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium text-green-600 dark:text-green-400">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                          Connected
                        </span>
                      </div>
                      <p className="text-[12px] text-[var(--text-3)] mt-1">{connector.description}</p>
                      {selected && (
                        <div className="mt-3 border-t border-[var(--border)] pt-3 space-y-2" onClick={e => e.stopPropagation()}>
                          <span className="text-[12px] font-semibold text-[var(--text-2)] block">
                            Granted permissions:
                          </span>
                          <div className="flex gap-4 flex-wrap">
                            {(connector.permissions ? Object.keys(connector.permissions) : ['read', 'write', 'delete']).map(action => {
                              const connPerms = connectorsPermissions[connector.provider_id]
                              const currentVal = connPerms?.[action] !== undefined ? connPerms[action] : true
                              return (
                                <label key={action} className="flex items-center gap-2 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={currentVal}
                                    onChange={e => {
                                      const checked = e.target.checked
                                      const categories = connector.permissions ? Object.keys(connector.permissions) : ['read', 'write', 'delete']
                                      setConnectorsPermissions(prev => {
                                        const existing = prev[connector.provider_id] || {}
                                        const base: Record<string, boolean> = {}
                                        for (const cat of categories) {
                                          base[cat] = existing[cat] !== undefined ? existing[cat] : true
                                        }
                                        base[action] = checked
                                        return {
                                          ...prev,
                                          [connector.provider_id]: base,
                                        }
                                      })
                                    }}
                                    className="w-4 h-4 accent-cyan-600 rounded"
                                  />
                                  <span className="text-[12px] font-medium text-[var(--text-2)] capitalize">
                                    {action}
                                  </span>
                                </label>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  </label>
                )
              })}
            </div>
            <Link href="/client/connectors" target="_blank">
              <Button variant="ghost" size="sm">Manage connector OAuth →</Button>
            </Link>
          </div>
          <div className="glass p-5 rounded-[var(--radius-lg)] h-fit sticky top-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-[14px] font-medium">Selected Connectors</span>
              <Badge variant="primary">{selectedConnectors.length}</Badge>
            </div>
            {selectedConnectors.length === 0 ? (
              <div className="border border-dashed border-[var(--border-2)] rounded-lg p-6 text-center text-[13px] text-[var(--text-3)]">No connectors selected</div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {selectedConnectors.map(c => (
                  <span key={c.id} className="inline-flex items-center gap-1 bg-cyan-100 text-cyan-700 dark:bg-cyan-900/50 dark:text-cyan-300 rounded-full px-2.5 py-1 text-[12px]">
                    {c.name}
                    <button type="button" onClick={() => update({ connectorIds: formData.connectorIds.filter(i => i !== c.id) })}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <p className="text-[11px] text-[var(--text-3)] mt-4">
              Only connectors with an active OAuth connection will execute at runtime. Each
              teammate who uses this agent must connect their own account for these
              connectors — connections are never shared across users, even for
              organization-wide connectors like Slack or Jira.
            </p>
          </div>
        </div>
      )}

      {/* Step 3 — MCP Servers */}
      {step === 3 && (
        <AgentMcpStep agentId={id} />
      )}

      {/* Step 5 — Review */}
      {step === 5 && (
        <div className="space-y-5">
          <div className="glass border border-violet-500/20 p-4 rounded-[var(--radius-lg)] flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            <span className="text-[14px] font-medium">Ready to save changes</span>
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
                <Button variant="ghost" size="xs" onClick={() => setStep(4)}>Edit</Button>
              </div>
              <p className="text-[12px] font-mono text-[var(--text-3)] line-clamp-4">{formData.prompt}</p>
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Tools ({selectedTools.length})</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(1)}>Edit</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedTools.length === 0
                  ? <span className="text-[13px] text-[var(--text-3)]">No tools attached</span>
                  : selectedTools.map(t => <Badge key={t.id} variant="neutral">{t.name ?? t.description}</Badge>)
                }
              </div>
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">Connectors ({selectedConnectors.length})</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(2)}>Edit</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedConnectors.length === 0
                  ? <span className="text-[13px] text-[var(--text-3)]">No connectors attached</span>
                  : selectedConnectors.map(c => <Badge key={c.id} variant="neutral">{c.name}</Badge>)
                }
              </div>
            </div>
            <div className="glass p-5 rounded-[var(--radius-lg)]">
              <div className="flex justify-between mb-3">
                <h4 className="font-medium">MCP Servers ({mcpServers.length})</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(3)}>Edit</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {mcpServers.length === 0
                  ? <span className="text-[13px] text-[var(--text-3)]">No MCP servers connected</span>
                  : mcpServers.map(s => (
                      <Badge key={s.id} variant={s.status === 'connected' ? 'success' : s.status === 'error' ? 'danger' : 'neutral'}>
                        {s.name || s.registry_key || 'Server'}
                      </Badge>
                    ))
                }
              </div>
            </div>
          </div>
          <Button variant="primary" size="lg" className="w-full" onClick={handleSave} disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
            Save Changes
          </Button>
        </div>
      )}

      {step < 5 && (
        <div className="flex justify-between mt-8">
          <Button variant="ghost" size="sm" onClick={() => setStep(s => Math.max(s - 1, 0))} disabled={step === 0}>
            <ArrowLeft className="w-4 h-4 mr-2" /> Back
          </Button>
          <Button variant="primary" size="sm" onClick={() => { if (validateStep()) setStep(s => Math.min(s + 1, 5)) }}>
            {step === 4 ? 'Review' : 'Next'} <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      )}
    </>
  )
}