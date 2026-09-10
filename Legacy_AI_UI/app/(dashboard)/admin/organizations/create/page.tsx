'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { FormField } from '@/components/ui/form-field'
import { useToast } from '@/hooks/use-toast'
import { organizationsApi } from '@/lib/api'
import { createOrganizationSchema } from '@/lib/validations/organization'

export default function CreateOrganizationPage() {
  const router = useRouter()
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', plan: 'starter' })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const updateField = (patch: Partial<typeof form>) => {
    setForm(f => ({ ...f, ...patch }))
    setFieldErrors(prev => {
      const next = { ...prev }
      for (const key of Object.keys(patch)) delete next[key]
      return next
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const result = createOrganizationSchema.safeParse({
      name: form.name,
      description: form.description || undefined,
    })
    if (!result.success) {
      const nextErrors: Record<string, string> = {}
      for (const issue of result.error.issues) {
        const key = issue.path[0]
        if (typeof key === 'string' && !nextErrors[key]) nextErrors[key] = issue.message
      }
      setFieldErrors(nextErrors)
      return
    }
    setFieldErrors({})

    setLoading(true)
    try {
      await organizationsApi.create(result.data)
      toast.success('Organization created')
      router.push('/admin/organizations')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create organization')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader title="Create Organization" description="Add a new organization to the platform" />

      <form
        onSubmit={handleSubmit}
        className="glass max-w-xl mx-auto p-6 rounded-[var(--radius-lg)] space-y-4"
      >
        <FormField label="Name" required error={fieldErrors.name}>
          <Input
            value={form.name}
            onChange={e => updateField({ name: e.target.value })}
            placeholder="Acme Corp"
          />
        </FormField>
        <FormField label="Description" error={fieldErrors.description}>
          <Textarea
            value={form.description}
            onChange={e => updateField({ description: e.target.value })}
            placeholder="Optional description"
          />
        </FormField>
        <FormField label="Plan" error={fieldErrors.plan}>
          <Select
            value={form.plan}
            onValueChange={v => updateField({ plan: v })}
            options={[
              { value: 'starter', label: 'Starter' },
              { value: 'pro', label: 'Pro' },
              { value: 'enterprise', label: 'Enterprise' },
            ]}
          />
        </FormField>
        <div className="flex justify-end gap-2 pt-2">
          <Link href="/admin/organizations">
            <Button type="button" variant="secondary">Cancel</Button>
          </Link>
          <Button type="submit" variant="primary" disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Create Organization
          </Button>
        </div>
      </form>
    </>
  )
}
