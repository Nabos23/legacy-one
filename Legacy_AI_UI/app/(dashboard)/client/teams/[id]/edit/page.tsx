'use client'

import { useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Users2, Shield, UserPlus, UserMinus, Save, Trash2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { PageHeader } from '@/components/ui/page-header'
import { FormField } from '@/components/ui/form-field'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/contexts/auth-context'
import { useUsers } from '@/hooks/use-users'
import { authApi, teamsApi } from '@/lib/api'
import type { PermissionDefinition, TeamPublic } from '@/types'

const humanizeResource = (resource: string) =>
  resource
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

export default function EditTeamPage() {
  const params = useParams()
  const teamId = params.id as string
  const router = useRouter()
  const { toast } = useToast()
  const { user, permissions } = useAuth()
  const orgId = user?.organization_id

  const [team, setTeam] = useState<TeamPublic | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedPermissions, setSelectedPermissions] = useState<Set<string>>(new Set())

  const [loading, setLoading] = useState(true)
  const [savingDetails, setSavingDetails] = useState(false)
  const [detailsErrors, setDetailsErrors] = useState<Record<string, string>>({})
  const [savingPermissions, setSavingPermissions] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [memberSearch, setMemberSearch] = useState('')
  const [addingMember, setAddingMember] = useState(false)
  const [removingMemberId, setRemovingMemberId] = useState<string | null>(null)

  const [catalog, setCatalog] = useState<PermissionDefinition[]>([])

  const { data: orgUsersData } = useUsers(1, orgId ?? undefined, undefined, undefined, 200)
  const allUsers = orgUsersData?.items ?? []

  // Load team data and permission catalog
  useEffect(() => {
    if (!teamId) return
    setLoading(true)

    Promise.all([
      teamsApi.get(teamId),
      teamsApi.getPermissions(teamId).catch(() => []),
      authApi.permissionCatalog().catch(() => []),
    ])
      .then(([teamData, permsData, catData]) => {
        setTeam(teamData)
        setName(teamData.name)
        setDescription(teamData.description || '')
        const effectivePerms = teamData.permissions?.length ? teamData.permissions : permsData
        setSelectedPermissions(new Set(effectivePerms || []))
        setCatalog(catData)
      })
      .catch(err => {
        console.error('Error loading team data:', err)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [teamId])

  const currentMembers = useMemo(() => {
    if (!team?.member_ids) return []
    const memberSet = new Set(team.member_ids)
    return allUsers.filter(u => u.id && memberSet.has(u.id))
  }, [team?.member_ids, allUsers])

  const nonMembers = useMemo(() => {
    if (!team?.member_ids) return allUsers
    const memberSet = new Set(team.member_ids)
    const available = allUsers.filter(u => u.id && !memberSet.has(u.id))
    if (!memberSearch.trim()) return available
    const q = memberSearch.toLowerCase()
    return available.filter(u => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))
  }, [team?.member_ids, allUsers, memberSearch])

  const groupedPermissions = useMemo(() => {
    const byResource = new Map<string, PermissionDefinition[]>()
    for (const p of catalog) {
      const list = byResource.get(p.resource) ?? []
      list.push(p)
      byResource.set(p.resource, list)
    }
    return [...byResource.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [catalog])

  const handleSaveDetails = async () => {
    if (!name.trim()) {
      setDetailsErrors({ name: 'Team name cannot be empty' })
      return
    }
    setDetailsErrors({})
    setSavingDetails(true)
    try {
      const updated = await teamsApi.update(teamId, {
        name: name.trim(),
        description: description.trim() || undefined,
      })
      setTeam(updated)
      toast.success('Team details updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update team details')
    } finally {
      setSavingDetails(false)
    }
  }

  const handleAddMember = async (userId: string) => {
    if (!userId) return
    setAddingMember(true)
    try {
      const updated = await teamsApi.addMembers(teamId, [userId])
      setTeam(updated)
      toast.success('Member added to team')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add member')
    } finally {
      setAddingMember(false)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    if (!userId) return
    setRemovingMemberId(userId)
    try {
      const updated = await teamsApi.removeMember(teamId, userId)
      setTeam(updated)
      toast.success('Member removed from team')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove member')
    } finally {
      setRemovingMemberId(null)
    }
  }

  const togglePermission = (permName: string) => {
    setSelectedPermissions(prev => {
      const next = new Set(prev)
      if (next.has(permName)) next.delete(permName)
      else next.add(permName)
      return next
    })
  }

  const handleSavePermissions = async () => {
    setSavingPermissions(true)
    try {
      const updated = await teamsApi.updatePermissions(teamId, [...selectedPermissions])
      setTeam(updated)
      setSelectedPermissions(new Set(updated.permissions || []))
      toast.success('Team permissions saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save team permissions')
    } finally {
      setSavingPermissions(false)
    }
  }

  const handleDeleteTeam = async () => {
    setDeleting(true)
    try {
      await teamsApi.remove(teamId)
      toast.success('Team deleted')
      router.push('/client/teams')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete team')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 max-w-4xl">
        <Skeleton className="h-10 w-48 rounded-lg" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    )
  }

  if (!team) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <p className="text-[16px] font-semibold text-[var(--text-1)]">Team Not Found</p>
        <Link href="/client/teams" className="mt-3 text-[13.5px] text-[var(--primary)] hover:underline">
          Return to Teams List
        </Link>
      </div>
    )
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
        title={`Edit Team: ${team.name}`}
        description="Update team information, manage members, and configure team permissions"
      />

      <div className="space-y-6 max-w-4xl">
        {/* Basic Information */}
        <div className="glass rounded-[var(--radius-lg)] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-semibold flex items-center gap-2">
              <Users2 className="w-4 h-4 text-[var(--primary)]" /> General Details
            </h3>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveDetails}
              disabled={savingDetails || !name.trim()}
            >
              {savingDetails ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
              Save Details
            </Button>
          </div>

          <FormField label="Team Name" error={detailsErrors.name}>
            <Input
              value={name}
              onChange={e => {
                setName(e.target.value)
                if (detailsErrors.name) setDetailsErrors(prev => ({ ...prev, name: '' }))
              }}
              placeholder="Team Name"
              className="text-[13.5px]"
              disabled={!permissions.edit_team}
            />
          </FormField>

          <FormField label="Description">
            <Textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Team Description..."
              className="text-[13.5px]"
              rows={3}
              disabled={!permissions.edit_team}
            />
          </FormField>
        </div>

        {/* Member Management */}
        <div className="glass rounded-[var(--radius-lg)] p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-semibold flex items-center gap-2">
              <Users2 className="w-4 h-4 text-[var(--primary)]" /> Team Members ({currentMembers.length})
            </h3>
          </div>

          {/* Current Members */}
          <div className="space-y-2">
            <label className="block text-[12.5px] font-semibold text-[var(--text-2)] uppercase tracking-wider">
              Current Members
            </label>
            {currentMembers.length === 0 ? (
              <p className="text-[13px] text-[var(--text-3)] py-2">No members in this team yet.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {currentMembers.map(m => {
                  const mid = m.id ?? ''
                  return (
                    <div
                      key={mid}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--surface-1)] border border-[var(--surface-3)]"
                    >
                      <div>
                        <p className="text-[13px] font-medium text-[var(--text-1)]">{m.name}</p>
                        <p className="text-[11.5px] text-[var(--text-3)]">{m.email}</p>
                      </div>
                      {permissions.edit_team && (
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => handleRemoveMember(mid)}
                          disabled={removingMemberId === mid}
                          title="Remove from team"
                        >
                          {removingMemberId === mid ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <UserMinus className="w-3.5 h-3.5 text-red-500" />
                          )}
                        </Button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Add Members Section */}
          {permissions.edit_team && (
            <div className="pt-3 border-t border-[var(--surface-3)] space-y-3">
              <label className="block text-[12.5px] font-semibold text-[var(--text-2)] uppercase tracking-wider">
                Add New Members
              </label>
              <div className="max-w-md">
                <SearchInput
                  value={memberSearch}
                  onChange={e => setMemberSearch(e.target.value)}
                  placeholder="Search available organization users..."
                />
              </div>

              <div className="max-h-48 overflow-y-auto space-y-1 pr-1 border border-[var(--surface-3)] rounded-lg p-2">
                {nonMembers.length === 0 ? (
                  <p className="text-[12.5px] text-[var(--text-3)] py-3 text-center">
                    {memberSearch ? 'No matching users found.' : 'All organization members belong to this team.'}
                  </p>
                ) : (
                  nonMembers.map(u => {
                    const uid = u.id ?? ''
                    if (!uid) return null
                    return (
                      <div
                        key={uid}
                        className="flex items-center justify-between p-2 rounded-md hover:bg-[var(--surface-2)] transition-colors"
                      >
                        <div>
                          <span className="text-[13px] font-medium block">{u.name}</span>
                          <span className="text-[11.5px] text-[var(--text-3)] block">{u.email}</span>
                        </div>
                        <Button
                          variant="secondary"
                          size="xs"
                          onClick={() => handleAddMember(uid)}
                          disabled={addingMember}
                        >
                          <UserPlus className="w-3.5 h-3.5 mr-1" /> Add
                        </Button>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Team Permissions Configuration */}
        <div className="glass rounded-[var(--radius-lg)] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-semibold flex items-center gap-2">
              <Shield className="w-4 h-4 text-[var(--primary)]" /> Team Permissions
            </h3>
            {permissions.edit_team && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleSavePermissions}
                disabled={savingPermissions}
              >
                {savingPermissions ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                )}
                Save Permissions
              </Button>
            )}
          </div>
          <p className="text-[13px] text-[var(--text-3)]">
            Permissions enabled here apply to all members of this team.
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
                        disabled={!permissions.edit_team}
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

        {/* Danger Zone */}
        {permissions.delete_team && (
          <div className="glass rounded-[var(--radius-lg)] p-6 border border-red-500/20 space-y-3">
            <h3 className="text-[15px] font-semibold text-red-600 dark:text-red-400">Danger Zone</h3>
            <p className="text-[13px] text-[var(--text-2)]">
              Deleting this team will soft-delete it and reset any agents or orchestrations assigned to it back to organization-wide visibility.
            </p>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setDeleteOpen(true)}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete Team
            </Button>
          </div>
        )}
      </div>

      {deleteOpen && (
        <Dialog
          open={true}
          onOpenChange={open => {
            if (!open) setDeleteOpen(false)
          }}
          title="Delete Team"
        >
          <div className="space-y-4">
            <p className="text-[13.5px] text-[var(--text-2)]">
              Are you sure you want to delete <span className="font-semibold text-[var(--text-1)]">{team.name}</span>?
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setDeleteOpen(false)} disabled={deleting}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleDeleteTeam} disabled={deleting} className="bg-red-600 hover:bg-red-700 text-white">
                {deleting ? 'Deleting…' : 'Delete Team'}
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </>
  )
}
