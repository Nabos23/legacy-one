'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Loader2, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { FormField } from '@/components/ui/form-field'
import { useToast } from '@/hooks/use-toast'
import { usersApi, authApi } from '@/lib/api'
import { createUserSchema } from '@/lib/validations/organization'
import { useAuth } from '@/contexts/auth-context'
import { useOrganizations } from '@/hooks/use-organizations'
import type { AssignableRole } from '@/types'

interface UserCreateFormProps {
  /** Route to navigate to after a successful create. */
  successPath: string
  /** Route the Cancel button links back to. */
  cancelPath: string
}

export function UserCreateForm({ successPath, cancelPath }: UserCreateFormProps) {
  const router = useRouter()
  const { toast } = useToast()
  const { user, permissions } = useAuth()

  const isSuperAdmin = permissions.is_super_admin === true
  const { data: orgsData } = useOrganizations(1, undefined, 1000)
  const orgs = orgsData?.items ?? []

  const [roleOptions, setRoleOptions] = useState<{ value: string; label: string }[]>([])
  useEffect(() => {
    authApi.assignableRoles()
      .then(roles => setRoleOptions(roles.map((r: AssignableRole) => ({ value: r.name, label: r.label }))))
      .catch(() => toast.error('Failed to load assignable roles'))
  }, [])

  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    role: 'user',
    organization_id: '',
  })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const clearFieldError = (key: string) =>
    setFieldErrors(prev => {
      if (!(key in prev)) return prev
      const { [key]: _omit, ...rest } = prev
      return rest
    })

  useEffect(() => {
    if (isSuperAdmin && orgs.length > 0 && !form.organization_id) {
      const defaultOrgId = (user?.organization_id && orgs.some(o => o.id === user.organization_id))
        ? user.organization_id
        : orgs[0].id!
      setForm(f => ({ ...f, organization_id: defaultOrgId }))
    }
  }, [isSuperAdmin, orgs, form.organization_id, user?.organization_id])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const payload = {
      ...form,
      organization_id: isSuperAdmin ? form.organization_id : (user?.organization_id ?? ''),
    }

    const result = createUserSchema.safeParse(payload)
    if (!result.success) {
      const errors: Record<string, string> = {}
      for (const issue of result.error.issues) {
        const key = issue.path[0]?.toString()
        if (key && !errors[key]) errors[key] = issue.message
      }
      setFieldErrors(errors)
      return
    }
    setFieldErrors({})

    setLoading(true)
    try {
      await usersApi.create(result.data)
      toast.success('User created successfully')
      router.push(successPath)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader title="Create User" description="Invite a new user to the platform" />

      <form
        onSubmit={handleSubmit}
        className="glass max-w-xl mx-auto p-6 rounded-[var(--radius-lg)] space-y-4"
      >
        <FormField label="Full Name" error={fieldErrors.name}>
          <Input
            value={form.name}
            onChange={e => {
              setForm(f => ({ ...f, name: e.target.value }))
              clearFieldError('name')
            }}
            placeholder="Jane Doe"
          />
        </FormField>
        <FormField label="Email" error={fieldErrors.email}>
          <Input
            type="email"
            value={form.email}
            onChange={e => {
              setForm(f => ({ ...f, email: e.target.value }))
              clearFieldError('email')
            }}
            placeholder="jane@company.com"
          />
        </FormField>
        <FormField label="Password" error={fieldErrors.password}>
          <Input
            type="password"
            value={form.password}
            onChange={e => {
              setForm(f => ({ ...f, password: e.target.value }))
              clearFieldError('password')
            }}
            placeholder="Min 6 characters"
          />
        </FormField>
        {isSuperAdmin && (
          <FormField label="Organization" required error={fieldErrors.organization_id}>
            <Select
              name="organization_id"
              required
              searchable
              searchPlaceholder="Search organization..."
              value={form.organization_id}
              onValueChange={v => {
                setForm(f => ({ ...f, organization_id: v }))
                clearFieldError('organization_id')
              }}
              options={orgs.map(org => ({ value: org.id!, label: org.name }))}
            />
          </FormField>
        )}
        <FormField label="Role" required error={fieldErrors.role}>
          <Select
            name="role"
            required
            value={form.role}
            onValueChange={v => {
              setForm(f => ({ ...f, role: v }))
              clearFieldError('role')
            }}
            options={roleOptions}
          />
        </FormField>
        <div className="flex justify-end gap-2 pt-2">
          <Link href={cancelPath}>
            <Button type="button" variant="secondary">Cancel</Button>
          </Link>
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <UserPlus className="w-4 h-4 mr-2" />
            )}
            Create User
          </Button>
        </div>
      </form>
    </>
  )
}
