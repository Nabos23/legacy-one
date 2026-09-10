'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Users2, Shield, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { PageHeader } from '@/components/ui/page-header'
import { FormField } from '@/components/ui/form-field'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/contexts/auth-context'
import { useUsers } from '@/hooks/use-users'
import { authApi, rolePermissionsApi, teamsApi } from '@/lib/api'
import type { PermissionDefinition } from '@/types'

const humanizeResource = (resource: string) =>
  resource
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

export default function CreateTeamPage() {
  const router = useRouter()
  const { toast } = useToast()
  const { user } = useAuth()
  const orgId = user?.organization_id

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set())
  const [selectedPermissions, setSelectedPermissions] = useState<Set<string>>(new Set())
  
  const [userSearch, setUserSearch] = useState('')
  const [catalog, setCatalog] = useState<PermissionDefinition[]>([])
  const [creating, setCreating] = useState(false)
  const [detailsErrors, setDetailsErrors] = useState<Record<string, string>>({})

  const { data: usersData, loading: loadingUsers } = useUsers(1, orgId ?? undefined, undefined, userSearch, 100)
  const users = usersData?.items ?? []

  // Load permission catalog & pre-fill default 'user' role permissions for the org
  useEffect(() => {
    authApi.permissionCatalog().then(setCatalog).catch(() => setCatalog([]))

    if (orgId) {
      rolePermissionsApi.get(orgId, 'user')
        .then(userRolePerms => {
          if (userRolePerms.permission_names && userRolePerms.permission_names.length > 0) {
            setSelectedPermissions(new Set(userRolePerms.permission_names))
          }
        })
        .catch(() => {})
    }
  }, [orgId])

  const groupedPermissions = useMemo(() => {
    const byResource = new Map<string, PermissionDefinition[]>()
    for (const p of catalog) {
      const list = byResource.get(p.resource) ?? []
      list.push(p)
      byResource.set(p.resource, list)
    }
    return [...byResource.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [catalog])

  const toggleMember = (id: string) => {
    if (!id) return
    setSelectedMemberIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const togglePermission = (permName: string) => {
    setSelectedPermissions(prev => {
      const next = new Set(prev)
      if (next.has(permName)) next.delete(permName)
      else next.add(permName)
      return next
    })
  }

  const handleCreate = async () => {
    if (!name.trim()) {
      setDetailsErrors({ name: 'Please enter a team name' })
      return
    }
    if (!orgId) {
      toast.error('Organization missing')
      return
    }
    setDetailsErrors({})

    setCreating(true)
    try {
      await teamsApi.create({
        organization_id: orgId,
        name: name.trim(),
        description: description.trim() || undefined,
        member_ids: [...selectedMemberIds],
        permissions: [...selectedPermissions],
      })
      toast.success('Team created successfully')
      router.push('/client/teams')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create team')
    } finally {
      setCreating(false)
    }
  }

  return (
    <>
      <div className="mb-4">
        <Link
          href="/client/teams"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--text-2)] hover:text-[var(--text-1)] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Teams
        </Link>
      </div>

      <PageHeader
        title="Create Team"
        description="Set up a new team, add members, and configure team-level permissions"
      />

      <div className="space-y-6 max-w-4xl">
        {/* Basic Details */}
        <div className="glass rounded-[var(--radius-lg)] p-6 space-y-4">
          <h3 className="text-[15px] font-semibold flex items-center gap-2">
            <Users2 className="w-4 h-4 text-[var(--primary)]" /> Basic Information
          </h3>

          <FormField label="Team Name" required error={detailsErrors.name}>
            <Input
              value={name}
              onChange={e => {
                setName(e.target.value)
                if (detailsErrors.name) setDetailsErrors(prev => ({ ...prev, name: '' }))
              }}
              placeholder="e.g. Data Engineering Team"
              className="text-[13.5px]"
            />
          </FormField>

          <FormField label="Description (Optional)">
            <Textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief description of this team's role or focus area..."
              className="text-[13.5px]"
              rows={3}
            />
          </FormField>
        </div>

        {/* Member Selection */}
        <div className="glass rounded-[var(--radius-lg)] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-semibold flex items-center gap-2">
              <Users2 className="w-4 h-4 text-[var(--primary)]" /> Add Initial Members
            </h3>
            <Badge variant="neutral">{selectedMemberIds.size} Selected</Badge>
          </div>

          <SearchInput
            value={userSearch}
            onChange={e => setUserSearch(e.target.value)}
            placeholder="Search members by name or email..."
          />

          <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1 border border-[var(--surface-3)] rounded-lg p-2">
            {loadingUsers ? (
              <p className="text-[13px] text-[var(--text-3)] py-4 text-center">Loading users...</p>
            ) : users.length === 0 ? (
              <p className="text-[13px] text-[var(--text-3)] py-4 text-center">No organization members found.</p>
            ) : (
              users.map(u => {
                const uid = u.id ?? ''
                if (!uid) return null
                const isSelected = selectedMemberIds.has(uid)
                return (
                  <div
                    key={uid}
                    onClick={() => toggleMember(uid)}
                    className={`flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-[var(--primary-subtle)] border border-[var(--primary)]/30'
                        : 'hover:bg-[var(--surface-2)]'
                    }`}
                  >
                    <div>
                      <p className="text-[13.5px] font-medium text-[var(--text-1)]">{u.name}</p>
                      <p className="text-[12px] text-[var(--text-3)]">{u.email}</p>
                    </div>
                    <Checkbox checked={isSelected} onChange={() => toggleMember(uid)} />
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Initial Team Permissions */}
        <div className="glass rounded-[var(--radius-lg)] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-semibold flex items-center gap-2">
              <Shield className="w-4 h-4 text-[var(--primary)]" /> Configure Team Permissions (Optional)
            </h3>
            <Badge variant={selectedPermissions.size > 0 ? 'primary' : 'neutral'}>
              {selectedPermissions.size} Permissions Selected
            </Badge>
          </div>
          <p className="text-[13px] text-[var(--text-3)]">
            Granting permissions here will make them accessible to all members of this team.
          </p>

          <div className="space-y-4 mt-3">
            {groupedPermissions.map(([resource, defs]) => (
              <div key={resource} className="p-4 rounded-lg bg-[var(--surface-1)] border border-[var(--surface-3)]">
                <h4 className="text-[13.5px] font-semibold mb-2.5">{humanizeResource(resource)}</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {defs.map(p => (
                    <label
                      key={p.name}
                      className="flex items-start gap-2.5 p-2 rounded-md cursor-pointer hover:bg-[var(--surface-2)]"
                    >
                      <Checkbox
                        checked={selectedPermissions.has(p.name)}
                        onChange={() => togglePermission(p.name)}
                      />
                      <span>
                        <span className="block text-[13px] font-medium">{p.label}</span>
                        <span className="block text-[11.5px] text-[var(--text-3)]">{p.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Submit Bar */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Link href="/client/teams">
            <Button variant="secondary" disabled={creating}>
              Cancel
            </Button>
          </Link>
          <Button variant="primary" onClick={handleCreate} disabled={creating || !name.trim()}>
            {creating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating Team...
              </>
            ) : (
              'Create Team'
            )}
          </Button>
        </div>
      </div>
    </>
  )
}
