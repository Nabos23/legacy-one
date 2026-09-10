'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Loader2, Building2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { PageHeader } from '@/components/ui/page-header'
import { FormField } from '@/components/ui/form-field'
import { useToast } from '@/hooks/use-toast'
import { organizationsApi } from '@/lib/api'
import { createOrganizationSchema } from '@/lib/validations/organization'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'

export default function EditOrganizationPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [form, setForm] = useState({ name: '', description: '' })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  useBreadcrumbLabel(id, form.name)

  const updateField = (patch: Partial<typeof form>) => {
    setForm(f => ({ ...f, ...patch }))
    setFieldErrors(prev => {
      const next = { ...prev }
      for (const key of Object.keys(patch)) delete next[key]
      return next
    })
  }

  useEffect(() => {
    organizationsApi.get(id)
      .then(org => setForm({ name: org.name ?? '', description: org.description ?? '' }))
      .catch(() => setNotFound(true))
      .finally(() => setFetching(false))
  }, [id])

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
      await organizationsApi.update(id, result.data)
      toast.success('Organization updated')
      router.push(`/admin/organizations/${id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update organization')
    } finally {
      setLoading(false)
    }
  }

  if (fetching) {
    return <div className="flex items-center justify-center h-64 text-[var(--text-3)]">Loading organization…</div>
  }

  if (notFound) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--text-3)]">
        <Building2 className="w-10 h-10" />
        <p>Organization not found</p>
        <Link href="/admin/organizations"><Button variant="ghost" size="sm">Back to Organizations</Button></Link>
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Edit Organization"
        description="Update organization details"
        actions={
          <Link href={`/admin/organizations/${id}`}>
            <Button variant="ghost" size="sm"><ArrowLeft className="w-4 h-4 mr-2" /> Back</Button>
          </Link>
        }
      />

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
        <div className="flex justify-end gap-2 pt-2">
          <Link href={`/admin/organizations/${id}`}>
            <Button type="button" variant="secondary">Cancel</Button>
          </Link>
          <Button type="submit" variant="primary" disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            Save Changes
          </Button>
        </div>
      </form>
    </>
  )
}
