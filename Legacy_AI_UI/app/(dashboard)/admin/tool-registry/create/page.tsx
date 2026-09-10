'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
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

type ToolType = 'db' | 'http' | 'rag' | 'custom'

interface SchemaPair { key: string; value: string }

export default function CreateToolRegistryPage() {
  const router = useRouter()
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    name: '',
    type: 'http' as ToolType,
    description: '',
    is_active: true,
  })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [schemaPairs, setSchemaPairs] = useState<SchemaPair[]>([{ key: '', value: '' }])

  const update = (patch: Partial<typeof form>) => {
    setForm(prev => ({ ...prev, ...patch }))
    setFieldErrors(prev => {
      const next = { ...prev }
      for (const key of Object.keys(patch)) delete next[key]
      return next
    })
  }

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
      await toolRegistryApi.create({
        name: form.name.trim(),
        type: form.type,
        description: form.description || undefined,
        is_active: form.is_active,
        tool_schema: Object.keys(tool_schema).length > 0 ? tool_schema : undefined,
      })
      toast.success('Tool type registered')
      router.push('/admin/tool-registry')
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Failed to register')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Add Tool Type"
        description="Register a new implementation in the tool catalog"
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
            {loading ? 'Registering…' : 'Register Tool Type'}
          </Button>
        </div>
      </div>
    </>
  )
}
