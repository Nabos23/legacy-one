'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Plus, Trash2, Package } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { InfoBox } from '@/components/ui/info-box'
import { Toggle } from '@/components/ui/toggle'
import { FormField } from '@/components/ui/form-field'
import { useToast } from '@/hooks/use-toast'
import { toolRegistryApi } from '@/lib/api'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'

type ToolType = 'db' | 'http' | 'rag' | 'custom'

interface SchemaPair { key: string; value: string }

export default function EditToolRegistryPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [form, setForm] = useState({
    name: '',
    type: 'http' as ToolType,
    description: '',
    is_active: true,
  })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  useBreadcrumbLabel(id, form.name)
  const [schemaPairs, setSchemaPairs] = useState<SchemaPair[]>([{ key: '', value: '' }])

  const update = (patch: Partial<typeof form>) => {
    setForm(prev => ({ ...prev, ...patch }))
    setFieldErrors(prev => {
      const next = { ...prev }
      for (const key of Object.keys(patch)) delete next[key]
      return next
    })
  }

  useEffect(() => {
    toolRegistryApi.get(id)
      .then(tool => {
        setForm({
          name: tool.name ?? '',
          type: (tool.type as ToolType) ?? 'http',
          description: tool.description ?? '',
          is_active: tool.is_active ?? true,
        })
        const pairs = Object.entries(tool.tool_schema ?? {}).map(([key, value]) => ({
          key,
          value: typeof value === 'string' ? value : String(value),
        }))
        setSchemaPairs(pairs.length > 0 ? pairs : [{ key: '', value: '' }])
      })
      .catch(() => setNotFound(true))
      .finally(() => setFetching(false))
  }, [id])

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      setFieldErrors(prev => ({ ...prev, name: 'Name is required' }))
      return
    }
    setFieldErrors({})
    const tool_schema = schemaPairs
      .filter(p => p.key.trim())
      .reduce<Record<string, string>>((acc, p) => {
        acc[p.key.trim()] = p.value.trim() || 'string'
        return acc
      }, {})

    setLoading(true)
    try {
      await toolRegistryApi.update(id, {
        name: form.name.trim(),
        type: form.type,
        description: form.description || undefined,
        is_active: form.is_active,
        tool_schema: Object.keys(tool_schema).length > 0 ? tool_schema : undefined,
      })
      toast.success('Tool type updated')
      router.push('/admin/tool-registry')
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Failed to update')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) {
    return <div className="flex items-center justify-center h-64 text-[var(--text-3)]">Loading tool…</div>
  }

  if (notFound) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--text-3)]">
        <Package className="w-10 h-10" />
        <p>Tool type not found</p>
        <Link href="/admin/tool-registry"><Button variant="ghost" size="sm">Back to Tool Registry</Button></Link>
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Edit Tool Type"
        description="Update this implementation in the tool catalog"
        actions={
          <Link href="/admin/tool-registry">
            <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-2" /> Tool Registry</Button>
          </Link>
        }
      />

      <div className="max-w-2xl mx-auto glass p-6 rounded-[var(--radius-lg)] space-y-5">
        <FormField label="Name" required error={fieldErrors.name}>
          <Input value={form.name} onChange={e => update({ name: e.target.value })} placeholder="sql-query-v2" />
        </FormField>

        <FormField label="Type" error={fieldErrors.type}>
          <Select
            value={form.type}
            onValueChange={v => update({ type: v as ToolType })}
            className="h-10"
            options={[
              { value: 'http', label: 'HTTP Endpoint' },
              { value: 'db', label: 'Database' },
              { value: 'rag', label: 'RAG Source' },
              { value: 'custom', label: 'Custom' },
            ]}
          />
        </FormField>

        <FormField label="Description" error={fieldErrors.description}>
          <Textarea
            value={form.description}
            onChange={e => update({ description: e.target.value })}
            placeholder="What does this tool do?"
          />
        </FormField>

        <div className="flex items-center justify-between">
          <span className="text-[13px] font-medium">Active</span>
          <Toggle checked={form.is_active} onChange={v => update({ is_active: v })} aria-label="Active" />
        </div>

        <div>
          <label className="text-[13px] font-medium block mb-2">Tool Schema</label>
          <InfoBox variant="info" className="mb-3">
            Define the expected input fields for this tool. Key = field name, Value = type (string / number / boolean / object).
          </InfoBox>
          <div className="space-y-2">
            {schemaPairs.map((pair, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Input
                  placeholder="field_name"
                  value={pair.key}
                  onChange={e => setSchemaPairs(prev => prev.map((p, j) => j === i ? { ...p, key: e.target.value } : p))}
                  className="flex-1"
                />
                <span className="text-[var(--text-3)] shrink-0">:</span>
                <Input
                  placeholder="string"
                  value={pair.value}
                  onChange={e => setSchemaPairs(prev => prev.map((p, j) => j === i ? { ...p, value: e.target.value } : p))}
                  className="flex-1"
                />
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setSchemaPairs(prev => prev.filter((_, j) => j !== i))}
                  disabled={schemaPairs.length === 1}
                  className="shrink-0 text-[var(--text-3)]"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              </div>
            ))}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSchemaPairs(prev => [...prev, { key: '', value: '' }])}
            >
              <Plus className="w-3.5 h-3.5 mr-1" /> Add field
            </Button>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-[var(--border)]">
          <Link href="/admin/tool-registry">
            <Button variant="secondary" size="sm">Cancel</Button>
          </Link>
          <Button variant="primary" size="sm" onClick={handleSubmit} disabled={loading}>
            {loading ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </>
  )
}
