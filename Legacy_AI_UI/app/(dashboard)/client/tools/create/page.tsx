'use client'

import { useState, useEffect, type FormEvent } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { CodeEditor } from '@/components/ui/code-editor'
import { InfoBox } from '@/components/ui/info-box'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { FormField } from '@/components/ui/form-field'
import { useToast } from '@/hooks/use-toast'
import { useAgents } from '@/hooks/use-agents'
import { useToolRegistry } from '@/hooks/use-tool-registry'
import { useAuth } from '@/contexts/auth-context'
import { toolsApi, agentsApi } from '@/lib/api'
import { createToolSchema } from '@/lib/validations/tool'
import { useOrganizations } from '@/hooks/use-organizations'
import { useDbConnections } from '@/hooks/use-db-connections'
import { formatToolName } from '@/lib/utils'

export default function CreateToolPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const prefilledAgentId = searchParams.get('agent_id') ?? ''
  const { toast } = useToast()
  const { user } = useAuth()
  const isSuperAdmin = user?.role === 'super_admin' || user?.role === 'super admin'
  const { data: orgsData } = useOrganizations(1, undefined, 1000)
  const orgs = orgsData?.items ?? []

  const { data: agentsData } = useAgents(1)
  const { data: registryData } = useToolRegistry(1)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    user_description: '',
    tool_id: '',
    name: '',
    agent_id: prefilledAgentId,
    organization_id: '',
    enabled: true,
  })


  const [credentials, setCredentials] = useState({
    api_key: '',
    base_url: '',
    model: '',
  })

  const [agentPrompt, setAgentPrompt] = useState('')
  const [agentGuardrails, setAgentGuardrails] = useState('')
  const [agentLoading, setAgentLoading] = useState(false)
  const [agentSaving, setAgentSaving] = useState(false)

  const [virtualDbMode, setVirtualDbMode] = useState<'none' | 'read' | 'write'>('none')
  const [dbConnId, setDbConnId] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const effectiveOrgId = isSuperAdmin ? form.organization_id : (user?.organization_id || '')
  const { data: dbConnData, loading: dbConnectionsLoading } = useDbConnections(1, effectiveOrgId || undefined, 100)
  const dbConnections = (dbConnData?.items ?? []).filter(c => !effectiveOrgId || c.organization_id === effectiveOrgId)

  const mongoReadTool = registryData?.items.find(r => r.name === 'query_mongo_read')
  const sqlReadTool = registryData?.items.find(r => r.name === 'query_sql_read')
  const mongoWriteTool = registryData?.items.find(r => r.name === 'query_mongo_write')
  const sqlWriteTool = registryData?.items.find(r => r.name === 'query_sql_write')

  const handleSelectTemplate = (selectedVal: string) => {
    setFieldErrors(prev => ({ ...prev, tool_id: '' }))
    if (selectedVal === 'virtual_db_read') {
      setVirtualDbMode('read')
      setDbConnId('')
      setForm(f => ({ ...f, tool_id: '' }))
    } else if (selectedVal === 'virtual_db_write') {
      setVirtualDbMode('write')
      setDbConnId('')
      setForm(f => ({ ...f, tool_id: '' }))
    } else {
      setVirtualDbMode('none')
      setDbConnId('')
      setForm(f => ({ ...f, tool_id: selectedVal }))
    }
  }

  const handleSelectDbConn = (connId: string) => {
    setFieldErrors(prev => ({ ...prev, db_conn_id: '' }))
    setDbConnId(connId)
    const conn = dbConnections.find(c => c.id === connId)
    if (!conn) return
    const connType = (conn.connection_type || '').toLowerCase()
    const isMongo = connType.includes('mongo') || (conn.connection_string || '').startsWith('mongodb')

    const targetTool = virtualDbMode === 'read'
      ? (isMongo ? mongoReadTool : sqlReadTool)
      : (isMongo ? mongoWriteTool : sqlWriteTool)

    if (targetTool?.id) {
      setForm(f => ({ ...f, tool_id: targetTool.id! }))
    }
  }

  const selectedRegistryEntry = registryData?.items.find(r => r.id === form.tool_id)
  const isGenerateImageTemplate = (() => {
    if (!selectedRegistryEntry) return false
    const key = `${selectedRegistryEntry.id ?? ''} ${selectedRegistryEntry.name ?? ''} ${selectedRegistryEntry.type ?? ''}`
      .toLowerCase()
      .replace(/[\s-]+/g, '_')
    return key.includes('generate_image')
  })()

  // Auto-select first org for super admins if none selected
  useEffect(() => {
    if (isSuperAdmin && orgs.length > 0 && !form.organization_id) {
      setForm(f => ({ ...f, organization_id: orgs[0].id! }))
    }
  }, [isSuperAdmin, orgs, form.organization_id])

  // Clear credentials if the user switches away from the generate_image template
  useEffect(() => {
    if (!isGenerateImageTemplate) {
      setCredentials({ api_key: '', base_url: '', model: '' })
    }
  }, [isGenerateImageTemplate])

  // Set default enabled state for permission depending on tool type name (query_db_write defaults to false)
  useEffect(() => {
    if (selectedRegistryEntry) {
      const templateName = selectedRegistryEntry.name || ''
      setForm(f => ({ ...f, enabled: templateName !== 'query_db_write' }))
    }
  }, [form.tool_id, selectedRegistryEntry])


  // Fetch selected agent's prompt and guardrails for inline editing
  useEffect(() => {
    let cancelled = false
    const aid = form.agent_id
    if (!aid) {
      setAgentPrompt('')
      setAgentGuardrails('')
      return
    }
    setAgentLoading(true)
    agentsApi.get(aid)
      .then(agent => {
        if (cancelled) return
        setAgentPrompt(agent.prompt || agent.instructions || '')
        setAgentGuardrails(agent.guardrails || '')
      })
      .catch(() => {
        if (!cancelled) toast.error('Failed to load agent prompt')
      })
      .finally(() => { if (!cancelled) setAgentLoading(false) })
    return () => { cancelled = true }
  }, [form.agent_id])

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (virtualDbMode !== 'none' && !dbConnId) {
      setFieldErrors(prev => ({ ...prev, db_conn_id: 'Select a database connection' }))
      return
    }
    if (!form.tool_id) {
      setFieldErrors(prev => ({ ...prev, tool_id: 'Select a valid tool template' }))
      return
    }

    const hasCredentials = isGenerateImageTemplate && (credentials.api_key || credentials.base_url || credentials.model)

    const payload = {
      organization_id: effectiveOrgId,
      agent_id: form.agent_id,
      tool_id: form.tool_id,
      db_conn_id: dbConnId || undefined,
      user_description: form.user_description,
      name: form.name || undefined,
      enabled: form.enabled,
      credentials: hasCredentials
        ? {
          api_key: credentials.api_key || undefined,
          base_url: credentials.base_url || undefined,
          model: credentials.model || undefined,
        }
        : undefined,
    }


    const result = createToolSchema.safeParse(payload)
    if (!result.success) {
      const errors: Record<string, string> = {}
      for (const issue of result.error.issues) {
        const key = String(issue.path[0] ?? '')
        if (key && !errors[key]) errors[key] = issue.message
      }
      setFieldErrors(errors)
      return
    }
    setFieldErrors({})

    setLoading(true)
    try {
      await toolsApi.create(payload)
      toast.success('Tool registered successfully')
      router.push('/client/tools')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to register tool')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Register Tool"
        description="Connect a tool from the registry to an agent"
      />

      <form
        onSubmit={handleSubmit}
        className="glass max-w-2xl mx-auto p-6 rounded-[var(--radius-lg)] space-y-4"
      >
        {isSuperAdmin && (
          <FormField label="Organization" required error={fieldErrors.organization_id}>
            <Select
              value={form.organization_id}
              onValueChange={v => {
                setForm(f => ({ ...f, organization_id: v }))
                setFieldErrors(prev => ({ ...prev, organization_id: '' }))
              }}
              placeholder="Select an organization"
              options={orgs.map(org => ({ value: org.id!, label: org.name }))}
            />
          </FormField>
        )}

        {/* Target Agent */}
        <FormField
          label="Target Agent"
          required
          hint="The agent this tool will be attached to"
          error={fieldErrors.agent_id}
        >
          <Select
            value={form.agent_id}
            onValueChange={v => {
              setForm(f => ({ ...f, agent_id: v }))
              setFieldErrors(prev => ({ ...prev, agent_id: '' }))
            }}
            placeholder="Select an agent"
            options={agentsData?.items.map(agent => ({ value: agent.id!, label: agent.name })) ?? []}
          />
        </FormField>

        {/* Edit Agent Prompt (when an agent is selected) */}
        {form.agent_id && (
          <div className="glass p-4 rounded-[var(--radius-lg)] space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-[13px] font-medium">Edit Agent Prompt</label>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={agentLoading || !form.agent_id}
                  onClick={async () => {
                    setAgentLoading(true)
                    try {
                      const agent = await agentsApi.get(form.agent_id)
                      setAgentPrompt(agent.prompt || agent.instructions || '')
                      setAgentGuardrails(agent.guardrails || '')
                      toast.success('Reloaded agent prompt')
                    } catch (e) {
                      toast.error('Failed to reload agent prompt')
                    } finally {
                      setAgentLoading(false)
                    }
                  }}
                >
                  {agentLoading ? 'Loading…' : 'Reload'}
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  disabled={agentSaving || !form.agent_id}
                  onClick={async () => {
                    setAgentSaving(true)
                    try {
                      await agentsApi.update(form.agent_id, { prompt: agentPrompt, guardrails: agentGuardrails } as any)
                      toast.success('Agent prompt saved')
                    } catch (e) {
                      toast.error(e instanceof Error ? e.message : 'Failed to save agent prompt')
                    } finally {
                      setAgentSaving(false)
                    }
                  }}
                >
                  {agentSaving ? 'Saving…' : 'Save Prompt'}
                </Button>
              </div>
            </div>
            <div>
              <CodeEditor value={agentPrompt} onChange={val => setAgentPrompt(val)} charLimit={4000} />
            </div>
            <FormField label="Guardrails">
              <InfoBox variant="info">Guardrails define safety rules enforced on every invocation.</InfoBox>
              <Textarea value={agentGuardrails} onChange={e => setAgentGuardrails(e.target.value)} />
            </FormField>
          </div>
        )}

        {/* Tool Registry Template */}
        <FormField
          label="Tool Registry Template"
          required
          hint="The base capabilities this tool will inherit"
          error={fieldErrors.tool_id}
        >
          <Select
            value={virtualDbMode !== 'none' ? `virtual_db_${virtualDbMode}` : form.tool_id}
            onValueChange={handleSelectTemplate}
            placeholder="Select a tool template"
            options={(() => {
              const active = registryData?.items.filter(r => r.is_active) ?? []
              const opts: { value: string; label: string }[] = []
              let addedRead = false
              let addedWrite = false
              for (const reg of active) {
                const isRead = ['query_mongo_read', 'query_sql_read', 'query_db_read', 'query_db'].includes(reg.name)
                const isWrite = ['query_mongo_write', 'query_sql_write', 'query_db_write'].includes(reg.name)
                if (isRead) {
                  if (!addedRead) {
                    opts.push({ value: 'virtual_db_read', label: 'Read from database (db_query)' })
                    addedRead = true
                  }
                } else if (isWrite) {
                  if (!addedWrite) {
                    opts.push({ value: 'virtual_db_write', label: 'Write to database (db_query)' })
                    addedWrite = true
                  }
                } else {
                  opts.push({ value: reg.id!, label: `${formatToolName(reg.name)} (${reg.type})` })
                }
              }
              return opts
            })()}
          />
        </FormField>

        {/* Database Connection Select (shown when a database template is selected) */}
        {virtualDbMode !== 'none' && (
          <FormField
            label="Database Connection"
            required
            error={fieldErrors.db_conn_id}
            hint={
              dbConnections.length === 0 && !dbConnectionsLoading
                ? 'No database connections available for this organization.'
                : undefined
            }
          >
            <Select
              value={dbConnId}
              onValueChange={handleSelectDbConn}
              placeholder={dbConnectionsLoading ? 'Loading connections...' : 'Select database connection'}
              options={dbConnections.map(conn => ({
                value: conn.id!,
                label: conn.name?.trim() || conn.connection_string,
              }))}
              disabled={dbConnectionsLoading || dbConnections.length === 0}
            />
          </FormField>
        )}

        {/* Custom image-model credentials — only shows for the generate_image template */}
        {isGenerateImageTemplate && (
          <div className="glass p-4 rounded-[var(--radius-lg)] space-y-3">
            <p className="text-[13px] font-medium">Custom image model (optional)</p>
            <p className="text-[11px] text-[var(--text-3)] -mt-2">
              Leave blank to use the organization default model.
            </p>
            <FormField label="API key">
              <Input
                type="password"
                value={credentials.api_key}
                onChange={e => setCredentials(c => ({ ...c, api_key: e.target.value }))}
                placeholder="sk-..."
              />
            </FormField>
            <FormField label="Base URL">
              <Input
                value={credentials.base_url}
                onChange={e => setCredentials(c => ({ ...c, base_url: e.target.value }))}
                placeholder="https://api.openai.com/v1"
              />
            </FormField>
            <FormField label="Model">
              <Input
                value={credentials.model}
                onChange={e => setCredentials(c => ({ ...c, model: e.target.value }))}
                placeholder="gpt-image-1"
              />
            </FormField>
          </div>
        )}

        {/* User Description */}
        <FormField
          label="User Description"
          required
          hint="Written for the AI (min 10 chars)"
          error={fieldErrors.user_description}
        >
          <Textarea
            value={form.user_description}
            onChange={e => {
              setForm(f => ({ ...f, user_description: e.target.value }))
              setFieldErrors(prev => ({ ...prev, user_description: '' }))
            }}
            placeholder="Describe what this tool does — written for the AI"
          />
        </FormField>

        {/* Optional display name */}
        <FormField label="Display Name" hint="Optional — shown in the UI" error={fieldErrors.name}>
          <Input
            value={form.name}
            onChange={e => {
              setForm(f => ({ ...f, name: e.target.value }))
              setFieldErrors(prev => ({ ...prev, name: '' }))
            }}
            placeholder="Optional friendly name"
          />
        </FormField>

        <div className="flex justify-end gap-2 pt-2">
          <Link href="/client/tools">
            <Button type="button" variant="secondary">Cancel</Button>
          </Link>
          <Button type="submit" variant="primary" disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Register Tool
          </Button>
        </div>
      </form>
    </>
  )
}