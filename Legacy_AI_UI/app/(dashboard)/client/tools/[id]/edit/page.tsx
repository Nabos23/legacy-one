'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { FormField } from '@/components/ui/form-field'
import { useToast } from '@/hooks/use-toast'
import { useToolRegistry } from '@/hooks/use-tool-registry'
import { toolsApi } from '@/lib/api'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import { useDbConnections } from '@/hooks/use-db-connections'
import { formatToolName } from '@/lib/utils'
import { useAuth } from '@/contexts/auth-context'

export default function EditToolPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()
  const { user } = useAuth()
  const { data: registryData } = useToolRegistry(1)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [form, setForm] = useState({
    user_description: '',
    tool_id: '',
    name: '',
  })
  useBreadcrumbLabel(id, form.name || form.user_description)
  const [hasCustomCredentials, setHasCustomCredentials] = useState(false)
  const [credentials, setCredentials] = useState({
    api_key: '',
    base_url: '',
    model: '',
  })

  const [agentId, setAgentId] = useState<string | undefined>()
  const [orgId, setOrgId] = useState<string | undefined>()

  const [virtualDbMode, setVirtualDbMode] = useState<'none' | 'read' | 'write'>('none')
  const [dbConnId, setDbConnId] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const effectiveOrgId = orgId || user?.organization_id || undefined
  const { data: dbConnData, loading: dbConnectionsLoading } = useDbConnections(1, effectiveOrgId, 100)
  const dbConnections = (dbConnData?.items ?? []).filter(c => !effectiveOrgId || c.organization_id === effectiveOrgId)

  const mongoReadTool = registryData?.items.find(r => r.name === 'query_mongo_read')
  const sqlReadTool = registryData?.items.find(r => r.name === 'query_sql_read')
  const mongoWriteTool = registryData?.items.find(r => r.name === 'query_mongo_write')
  const sqlWriteTool = registryData?.items.find(r => r.name === 'query_sql_write')

  const selectedRegistryEntry = registryData?.items.find(r => r.id === form.tool_id)
  const toolName = form.name || selectedRegistryEntry?.name || ''
  const isGenerateImageTemplate = (() => {
    if (!selectedRegistryEntry) return false
    const key = `${selectedRegistryEntry.id ?? ''} ${selectedRegistryEntry.name ?? ''} ${selectedRegistryEntry.type ?? ''}`
      .toLowerCase()
      .replace(/[\s-]+/g, '_')
    return key.includes('generate_image')
  })()

  useEffect(() => {
    toolsApi
      .get(id)
      .then(tool => {
        setForm({
          user_description: tool.user_description ?? '',
          tool_id: tool.tool_id ?? '',
          name: tool.name ?? '',
        })
        setAgentId(tool.agent_id)
        setOrgId(tool.organization_id)
        setHasCustomCredentials(Boolean(tool.has_custom_credentials))
        if (tool.db_conn_id) {
          setDbConnId(tool.db_conn_id)
        }
      })
      .catch(() => toast.error('Failed to load tool'))
      .finally(() => setFetching(false))
  }, [id])

  useEffect(() => {
    if (selectedRegistryEntry) {
      const regName = selectedRegistryEntry.name || ''
      if (['query_mongo_read', 'query_sql_read', 'query_db_read', 'query_db'].includes(regName)) {
        setVirtualDbMode('read')
      } else if (['query_mongo_write', 'query_sql_write', 'query_db_write'].includes(regName)) {
        setVirtualDbMode('write')
      } else {
        setVirtualDbMode('none')
      }
    }
  }, [selectedRegistryEntry])

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


  const update = (patch: Partial<typeof form>) => {
    setForm(prev => ({ ...prev, ...patch }))
    setFieldErrors(prev => {
      const next = { ...prev }
      for (const key of Object.keys(patch)) delete next[key]
      return next
    })
  }

  const handleSave = async () => {
    const errors: Record<string, string> = {}
    if (!form.user_description.trim()) {
      errors.user_description = 'User description is required'
    }
    if (virtualDbMode !== 'none' && !dbConnId) {
      errors.db_conn_id = 'Select a database connection'
    }
    if (!form.tool_id.trim()) {
      errors.tool_id = 'Select a valid tool template'
    }
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }
    setFieldErrors({})
    setLoading(true)
    try {
      const hasNewCredentials = isGenerateImageTemplate && (credentials.api_key || credentials.base_url || credentials.model)
      await toolsApi.update(id, {
        user_description: form.user_description,
        tool_id: form.tool_id,
        db_conn_id: dbConnId || undefined,
        name: form.name || undefined,
        credentials: hasNewCredentials
          ? {
              api_key: credentials.api_key || undefined,
              base_url: credentials.base_url || undefined,
              model: credentials.model || undefined,
            }
          : undefined,
      })

      toast.success('Tool updated')
      router.push('/client/tools')

    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Failed to update tool')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) {
    return <div className="flex items-center justify-center h-64 text-[var(--text-3)]">Loading tool…</div>
  }

  return (
    <>
      <PageHeader
        title="Edit Tool"
        actions={
          <Link href="/client/tools">
            <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-2" /> Tools</Button>
          </Link>
        }
      />

      <div className="max-w-2xl mx-auto glass p-6 rounded-[var(--radius-lg)] space-y-5">
        <FormField
          label="User Description"
          required
          hint="Describe this tool for the AI agent"
          error={fieldErrors.user_description}
        >
          <Textarea value={form.user_description} onChange={e => update({ user_description: e.target.value })} rows={3} />
        </FormField>

        <FormField
          label="Tool Registry Template"
          required
          hint="The base capabilities this tool inherits"
          error={fieldErrors.tool_id}
        >
          <Select
            value={virtualDbMode !== 'none' ? `virtual_db_${virtualDbMode}` : form.tool_id}
            onValueChange={handleSelectTemplate}
            placeholder="Select a tool template"
            className="h-10"
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
                : 'Select which connected database this tool executes queries against'
            }
          >
            <Select
              value={dbConnId}
              onValueChange={handleSelectDbConn}
              placeholder={dbConnectionsLoading ? 'Loading connections...' : 'Select database connection'}
              className="h-10"
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
          <div className="glass p-4 rounded-[var(--radius-lg)] space-y-3 border border-[var(--border)]">
            <p className="text-[13px] font-medium">Custom image model (optional)</p>
            <p className="text-[11px] text-[var(--text-3)] -mt-2">
              Leave blank to use the organization default model.
            </p>
            <FormField label="API key">
              <Input
                type="password"
                value={credentials.api_key}
                onChange={e => setCredentials(c => ({ ...c, api_key: e.target.value }))}
                placeholder={hasCustomCredentials ? '•••••••• (saved — leave blank to keep)' : 'sk-...'}
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
            {hasCustomCredentials && (
              <p className="text-[11px] text-[var(--text-3)]">
                A custom API key is already saved for this tool. Fields left blank keep the current saved value.
              </p>
            )}
          </div>
        )}

        <FormField label="Display Name" hint="Optional — defaults to registry name" error={fieldErrors.name}>
          <Input value={form.name} onChange={e => update({ name: e.target.value })} placeholder="Defaults to registry name" />
        </FormField>

        <div className="flex justify-end gap-3 pt-2 border-t border-[var(--border)]">
          <Link href="/client/tools">
            <Button variant="secondary" size="sm">Cancel</Button>
          </Link>
          <Button variant="primary" size="sm" onClick={handleSave} disabled={loading}>
            {loading ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </>
  )
}