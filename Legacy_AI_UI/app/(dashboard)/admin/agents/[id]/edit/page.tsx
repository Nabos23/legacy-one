'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, ArrowRight, CheckCircle2, Database, Loader2, Save, Sparkles, Wrench, X,
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
import { AgentMcpStep } from '@/components/mcp/agent-mcp-step'
import { useToast } from '@/hooks/use-toast'
import { useToolRegistry } from '@/hooks/use-tool-registry'
import { useDbConnections } from '@/hooks/use-db-connections'
import { useMcpServersByAgent } from '@/hooks/use-mcp-servers'
import { useUsers } from '@/hooks/use-users'
import { useAgentPermissions } from '@/hooks/use-agent-permissions'
import { useAuth } from '@/contexts/auth-context'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import { agentsApi, promptGeneratorApi, toolsApi } from '@/lib/api'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'
import { AgentAvatarPicker, buildAvatarApiPayload, getAvatarDisplayProps, normalizeAvatarSelection, type AgentAvatarSelection } from '@/components/dashboard/agent-avatar-picker'
import { DEFAULT_AGENT_STICKER_ID } from '@/lib/agent-stickers'
import { agentVisibilityLabel, formatToolName } from '@/lib/utils'
import type { AgentAvatarType } from '@/types'

const STEPS = ['Identity', 'Tools', 'MCP Servers', 'Prompt & Guardrails', 'Review']

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
  ownerScope: 'user' | 'organization' | 'selected_users' | 'team'
  allowedUserIds: string[]
}

export default function AdminEditAgentPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()
  const { user } = useAuth()
  // /admin is super_admin-only (see DashboardLayout's isAdminUser check) --
  // org_admin/org_manager use /client/agents/.../edit instead, so there's no
  // reachable case where they land on this page.
  const canChooseVisibility = user?.role === 'super_admin' || user?.role === 'super admin'
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [uploadingAvatar, setUploadingAvatar] = useState(false)
  const [generatingPrompt, setGeneratingPrompt] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const [toolSearch, setToolSearch] = useState('')
  const [userSearch, setUserSearch] = useState('')
  const [pageSize, setPageSize] = useState(100)
  const [page, setPage] = useState(1)
  const [organizationId, setOrganizationId] = useState('')
  const { data: toolsData, loading: toolsLoading } = useToolRegistry(page, pageSize, { isActive: true, sortBy: 'name', sortOrder: 'asc' })
  const allTools = toolsData?.items ?? []
  const { data: mcpServers } = useMcpServersByAgent(id)
  const { data: orgUsersData } = useUsers(1, organizationId || undefined, undefined, undefined, 100, {}, canChooseVisibility)
  const orgUsers = (orgUsersData?.items ?? []).filter(u => u.id !== user?.id)
  const filteredOrgUsers = orgUsers.filter(u =>
    `${u.name} ${u.email}`.toLowerCase().includes(userSearch.toLowerCase())
  )
  const { permissions, setPermissions, connectorsPermissions, updatePermissions } = useAgentPermissions(id)
  const [toolRecordIdsByRegistryId, setToolRecordIdsByRegistryId] = useState<Record<string, string>>({})
  const [formData, setFormData] = useState<FormData>({
    name: '', description: '', avatarType: 'sticker', avatarValue: DEFAULT_AGENT_STICKER_ID, avatarUrl: null, avatarPreviewUrl: null,
    prompt: '', guardrails: '', toolIds: [], toolDbConnectionIds: {}, ownerScope: 'organization', allowedUserIds: [],
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
        const dbConnIds: Record<string, string> = {}
        const registryToolIds: string[] = []

        for (const inst of validInstances) {
          if (inst && inst.tool_id) {
            recordIdsMap[inst.tool_id] = inst.id!
            registryToolIds.push(inst.tool_id)
            if (inst.db_conn_id) {
              dbConnIds[inst.tool_id] = inst.db_conn_id
            }
          }
        }

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
          toolDbConnectionIds: dbConnIds,
          ownerScope: agent.owner_scope ?? 'organization',
          allowedUserIds: agent.allowed_user_ids ?? [],
        })
      })
      .catch(() => toast.error('Failed to load agent'))
      .finally(() => setFetching(false))
  }, [id])



  const isAskHumanTool = (tool: (typeof allTools)[number]) => {
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
    if (step === 3 && formData.prompt.trim().length < 10) errs.prompt = 'System prompt must be at least 10 characters'
    if (step === 3 && formData.guardrails.trim().length < 10) errs.guardrails = 'Guardrails must be at least 10 characters'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const selectedOrganizationId = organizationId || user?.organization_id || ''
  const { data: dbConnectionsData, loading: dbConnectionsLoading } = useDbConnections(1, selectedOrganizationId || undefined, 100)
  const dbConnections = (dbConnectionsData?.items ?? []).filter(conn => !selectedOrganizationId || conn.organization_id === selectedOrganizationId)
  const dbConnectionLabel = (conn: (typeof dbConnections)[number]) =>
    conn.name?.trim() || conn.connection_string

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

  const isDbQueryTool = isRawDbTool

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

      if (!toolRecordId) {
        const created = await toolsApi.create({
          organization_id: orgId,
          agent_id: id,
          tool_id: tool.id,
          user_description: tool.description || `${tool.name} tool`,
          name: tool.name,
          db_conn_id: dbConnId,
          enabled: permissions[tool.name!] !== undefined ? permissions[tool.name!] : tool.name !== 'query_db_write',
        })
        toolRecordId = created.id!
        nextToolRecords[tool.id] = toolRecordId
      } else if (isRawDbTool(tool)) {
        await toolsApi.update(toolRecordId, { db_conn_id: dbConnId })
      }

      nextAttachedToolIds.push(toolRecordId)
    }

    setToolRecordIdsByRegistryId(nextToolRecords)
    return nextAttachedToolIds
  }

  const handleSave = async () => {
    setLoading(true)
    try {
      const syncedToolIds = await syncSelectedTools()
      await agentsApi.update(id, {
        name: formData.name,
        description: formData.description || undefined,
        prompt: formData.prompt,
        guardrails: formData.guardrails,
        tool_ids: syncedToolIds,
        allowed_user_ids: canChooseVisibility && formData.ownerScope === 'selected_users' ? formData.allowedUserIds : undefined,
        ...buildAvatarApiPayload(avatarSelection),
      })
      const permissionsPatch = { ...permissions }
      for (const tool of selectedTools) {
        if (tool.name) {
          permissionsPatch[tool.name] = isAskHumanTool(tool)
            ? true
            : (permissions[tool.name] !== undefined ? permissions[tool.name] : tool.name !== 'query_db_write')
        }
      }
      await updatePermissions(permissionsPatch, connectorsPermissions)
      toast.success('Agent updated successfully')
      router.push('/admin/agents')
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Failed to update agent')
    } finally {
      setLoading(false)
    }
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
    (t.name ?? t.description ?? '').toLowerCase().includes(toolSearch.toLowerCase())
  )

  const filteredVirtualTools = virtualTools.filter(vt =>
    `${vt.name} ${vt.description}`.toLowerCase().includes(toolSearch.toLowerCase())
  )

  const filteredTools = filteredStandardTools
  const selectedTools = allTools.filter(t => formData.toolIds.includes(t.id!))

  if (fetching) {
    return <div className="flex items-center justify-center h-64 text-[var(--text-3)]">Loading agent…</div>
  }

  return (
    <>
      <PageHeader
        title="Edit Agent"
        description="Update your agent's configuration"
        actions={
          <Link href="/admin/agents">
            <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-2" /> Agents</Button>
          </Link>
        }
      />

      <div className="mb-8">
        <Stepper steps={STEPS} currentStep={step} />
      </div>

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
      {step === 3 && (
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
          <div className="glass p-5 rounded-[var(--radius-lg)] space-y-3">
            <FormField label="Guardrails" error={errors.guardrails}>
              <InfoBox variant="info">Guardrails define safety rules enforced on every invocation.</InfoBox>
              <Textarea
                value={formData.guardrails}
                onChange={e => update({ guardrails: e.target.value })}
                placeholder="Never share PII. Refuse harmful requests…"
                className={errors.guardrails ? 'border-red-400 focus-visible:ring-red-400' : ''}
              />
            </FormField>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <SearchInput value={toolSearch} onChange={e => setToolSearch(e.target.value)} placeholder="Search tools…" />
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
                        <FormField label="Database connection">
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
          </div>
        </div>
      )}

      {step === 2 && (
        <AgentMcpStep agentId={id} />
      )}

      {step === 4 && (
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
                <Button variant="ghost" size="xs" onClick={() => setStep(3)}>Edit</Button>
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
                <h4 className="font-medium">MCP Servers ({mcpServers.length})</h4>
                <Button variant="ghost" size="xs" onClick={() => setStep(2)}>Edit</Button>
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

      {step < 4 && (
        <div className="flex justify-between mt-8">
          <Button variant="ghost" size="sm" onClick={() => setStep(s => Math.max(s - 1, 0))} disabled={step === 0}>
            <ArrowLeft className="w-4 h-4 mr-2" /> Back
          </Button>
          <Button variant="primary" size="sm" onClick={() => { if (validateStep()) setStep(s => Math.min(s + 1, 4)) }}>
            {step === 3 ? 'Review' : 'Next'} <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      )}
    </>
  )
}
