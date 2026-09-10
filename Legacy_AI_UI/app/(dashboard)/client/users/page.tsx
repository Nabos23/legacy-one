'use client'

import { useEffect, useMemo, useState } from 'react'
import { X, SlidersHorizontal, Users, Edit2, Trash2, Check, Clock } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { DataTable, type Column } from '@/components/ui/data-table'
import { Pagination } from '@/components/ui/pagination'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/empty-state'
import { Tabs } from '@/components/ui/tabs'
import { UserEditDialog } from '@/components/users/user-edit-dialog'
import { UserDeleteDialog } from '@/components/users/user-delete-dialog'
import { TeamsPanel } from '@/components/teams/teams-panel'
import { useUsers } from '@/hooks/use-users'
import { useTeams } from '@/hooks/use-teams'
import { useOrganizations } from '@/hooks/use-organizations'
import { useUserEditDelete } from '@/hooks/use-user-edit-delete'
import { useToast } from '@/hooks/use-toast'
import { formatDate, avatarColor, normalizeRoleName } from '@/lib/utils'
import { useAuth } from '@/contexts/auth-context'
import { authApi, teamsApi } from '@/lib/api'
import type { UserPublic, AssignableRole } from '@/types'

export default function UsersPage() {
  const { permissions, user } = useAuth()
  const { toast } = useToast()

  // super_admin → global /users list; everyone else → org-scoped /organizations/{id}/users
  const orgId = permissions.is_super_admin ? undefined : (user?.organization_id ?? undefined)
  const { data, loading, error, page, setPage, refetch } = useUsers(1, orgId)
  const { data: teamsData, loading: loadingTeams, refetch: refetchTeams } = useTeams(1, orgId, undefined, 100)
  const teams = teamsData?.items ?? []
  const { data: orgsData } = useOrganizations(1, undefined, 1000)

  const isOrgAdmin = user?.role === 'org_admin' || permissions.is_super_admin
  const [showPendingOnly, setShowPendingOnly] = useState(false)
  const [pendingUsers, setPendingUsers] = useState<UserPublic[]>([])
  const [loadingPending, setLoadingPending] = useState(false)
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)
  const [teamUpdatingUserId, setTeamUpdatingUserId] = useState<string | null>(null)

  const fetchPendingUsers = async () => {
    if (!isOrgAdmin) return
    setLoadingPending(true)
    try {
      const res = await authApi.pendingApprovals()
      setPendingUsers(res)
    } catch (err) {
      console.error('Failed to fetch pending approvals', err)
      setPendingUsers([])
    } finally {
      setLoadingPending(false)
    }
  }

  useEffect(() => {
    if (isOrgAdmin) {
      fetchPendingUsers()
    }
  }, [isOrgAdmin])

  const handleApprove = async (userId: string) => {
    setActionLoadingId(userId)
    try {
      await authApi.updateApproval(userId, 'approved')
      await fetchPendingUsers()
      refetch()
    } catch (err) {
      console.error('Approval failed', err)
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleDisapprove = async (userId: string) => {
    setActionLoadingId(userId)
    try {
      await authApi.updateApproval(userId, 'disapproved')
      await fetchPendingUsers()
      refetch()
    } catch (err) {
      console.error('Disapproval failed', err)
    } finally {
      setActionLoadingId(null)
    }
  }

  const showTeamsTab = permissions.is_super_admin || permissions.view_team
  const [activeTab, setActiveTab] = useState<'users' | 'teams'>('users')

  const [roleFilterOptions, setRoleFilterOptions] = useState<AssignableRole[]>([])
  useEffect(() => {
    authApi.assignableRoles().then(setRoleFilterOptions).catch(() => setRoleFilterOptions([]))
  }, [])

  const [allRoles, setAllRoles] = useState<AssignableRole[]>([])
  useEffect(() => {
    authApi.allRoles().then(setAllRoles).catch(() => setAllRoles([]))
  }, [])

  const adminRoleNames = useMemo(
    () => new Set(allRoles.filter(r => r.is_admin).map(r => normalizeRoleName(r.name))),
    [allRoles],
  )

  const {
    editTarget, editForm, setEditForm, saving, openEdit, handleEditSave, closeEdit,
    deleteTarget, deleting, setDeleteTarget, handleDelete,
  } = useUserEditDelete(refetch)

  const orgNameMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const org of orgsData?.items ?? []) {
      if (org.id) map[org.id] = org.name
    }
    return map
  }, [orgsData?.items])

  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('all')

  const users = useMemo(() => {
    const items = showPendingOnly ? pendingUsers : (data?.items ?? [])
    return items.filter(u => {
      if (u.waiting_approval === 'disapproved') return false
      const q = search.toLowerCase()
      const matchSearch = !q || 
        u.name.toLowerCase().includes(q) || 
        u.email.toLowerCase().includes(q)
      const matchRole = roleFilter === 'all' || u.role === roleFilter
      
      return matchSearch && matchRole
    })
  }, [data?.items, pendingUsers, showPendingOnly, search, roleFilter])

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handleRoleChange = (val: string) => {
    setRoleFilter(val)
    setPage(1)
  }

  const handleTeamChange = async (user: UserPublic, newTeamId: string) => {
    if (!user.id) return
    const userId = user.id
    setTeamUpdatingUserId(userId)

    const currentTeam = teams.find(t => t.member_ids?.includes(userId))

    try {
      if (currentTeam && currentTeam.id && currentTeam.id !== newTeamId) {
        await teamsApi.removeMember(currentTeam.id, userId)
      }

      if (newTeamId && newTeamId !== 'none') {
        await teamsApi.addMembers(newTeamId, [userId])
        toast.success(`Assigned ${user.name} to team`)
      } else if (currentTeam) {
        toast.success(`Removed ${user.name} from team`)
      }

      refetchTeams()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update team membership')
    } finally {
      setTeamUpdatingUserId(null)
    }
  }

  const columns: Column<UserPublic>[] = [
    {
      key: 'name',
      header: 'Name',
      render: row => (
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-full ${avatarColor(row.name)} flex items-center justify-center text-white text-xs font-semibold`}>
            {row.name.split(' ').map((n: string) => n[0]).join('')}
          </div>
          <span className="font-medium">{row.name}</span>
        </div>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      render: row => <span className="text-[13px] text-[var(--text-2)]">{row.email}</span>,
    },
    {
      key: 'team',
      header: 'Team',
      render: row => {
        const userId = row.id ?? ''
        const userTeam = teams.find(t => t.member_ids?.includes(userId))
        const currentTeamId = userTeam?.id ?? 'none'
        const isUpdating = teamUpdatingUserId === userId

        if (!permissions.edit_team && !isOrgAdmin) {
          return (
            <Badge variant={userTeam ? 'primary' : 'neutral'}>
              {userTeam ? userTeam.name : 'None'}
            </Badge>
          )
        }

        const options = [
          { value: 'none', label: 'None' },
          ...teams.map(t => ({ value: t.id ?? '', label: t.name })),
        ]

        return (
          <div className="w-36">
            <Select
              value={currentTeamId}
              onValueChange={v => handleTeamChange(row, v)}
              options={options}
              disabled={isUpdating || loadingTeams}
            />
          </div>
        )
      },
    },
    {
      key: 'role',
      header: 'Role',
      render: row => (
        <Badge variant={adminRoleNames.has(normalizeRoleName(row.role)) ? 'primary' : 'neutral'} className="capitalize">
          {row.role}
        </Badge>
      ),
    },
    {
      key: 'organization_id',
      header: 'Organization',
      render: row => (
        <span className="text-[13px] text-[var(--text-2)]">
          {orgNameMap[row.organization_id] ?? row.organization_id.slice(-8)}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Joined',
      render: row => <span className="text-[13px] text-[var(--text-3)]">{formatDate(row.created_at)}</span>,
    },
    ...(permissions.edit_user || permissions.delete_user || isOrgAdmin
      ? [
          {
            key: 'actions',
            header: 'Actions',
            render: (row: UserPublic) => {
              if (showPendingOnly) {
                const isProcessing = actionLoadingId === row.id
                return (
                  <div className="flex items-center gap-2">
                    <Button
                      size="xs"
                      disabled={isProcessing}
                      onClick={() => handleApprove(row.id!)}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium gap-1 text-[12px] px-2.5 py-1"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Approve
                    </Button>
                    <Button
                      size="xs"
                      variant="outline"
                      disabled={isProcessing}
                      onClick={() => handleDisapprove(row.id!)}
                      className="text-red-600 dark:text-red-400 hover:bg-red-500/10 border-red-200 dark:border-red-800/40 gap-1 text-[12px] px-2.5 py-1"
                    >
                      <X className="w-3.5 h-3.5" />
                      Reject
                    </Button>
                  </div>
                )
              }
              return (
                <div className="flex items-center gap-1">
                  {permissions.edit_user && (
                    <Button variant="ghost" size="xs" onClick={() => openEdit(row)} title="Edit">
                      <Edit2 className="w-4 h-4" />
                    </Button>
                  )}
                  {permissions.delete_user && row.id !== user?.id && (
                    <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)} title="Delete">
                      <Trash2 className="w-4 h-4 text-red-500 dark:text-red-400" />
                    </Button>
                  )}
                </div>
              )
            },
          } as Column<UserPublic>,
        ]
      : []),
  ]

  const totalLoaded = showPendingOnly ? pendingUsers.length : (data?.items.length ?? 0)
  const isFiltering = search.trim() || roleFilter !== 'all'
  const showingFiltered = isFiltering && users.length !== totalLoaded

  return (
    <>
      <PageHeader
        title="Users"
        description="Manage system users, teams, and permissions"
        actions={
          activeTab === 'users' && permissions.create_user ? (
            <Link href="/client/users/create">
              <CreateButton>Create User</CreateButton>
            </Link>
          ) : undefined
        }
      />

      {showTeamsTab && (
        <Tabs
          className="mb-5"
          value={activeTab}
          onChange={v => setActiveTab(v as 'users' | 'teams')}
          tabs={[
            { value: 'users', label: 'Users' },
            { value: 'teams', label: 'Teams' },
          ]}
        />
      )}

      {activeTab === 'teams' ? (
        <TeamsPanel orgId={orgId} />
      ) : (
      <>
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => handleSearchChange(e.target.value)}
          placeholder="Search users..."
          className="max-w-[280px]"
        />

        <Select
          value={roleFilter}
          onValueChange={handleRoleChange}
          className="w-44"
          options={[
            { value: 'all', label: 'All roles' },
            ...roleFilterOptions.map(r => ({ value: r.name, label: r.label })),
          ]}
        />

        {isOrgAdmin && (
          <button
            type="button"
            onClick={() => {
              setShowPendingOnly(!showPendingOnly)
              setPage(1)
            }}
            className={`px-3 py-1.5 rounded-xl text-[13px] font-medium transition-all border flex items-center gap-2 ${
              showPendingOnly
                ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 ring-2 ring-amber-500/20'
                : 'bg-card hover:bg-accent/50 text-[var(--text-2)] border-border'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Pending Approvals</span>
            {pendingUsers.length > 0 && (
              <span className="px-1.5 py-0.5 text-[11px] font-bold rounded-full bg-amber-500 text-white">
                {pendingUsers.length}
              </span>
            )}
          </button>
        )}


        {showingFiltered && (
          <span className="text-[13px] text-[var(--text-3)]">
            Showing <strong className="text-[var(--text-1)]">{users.length}</strong> of {totalLoaded}
          </span>
        )}
        
        {isFiltering && (
          <button
            onClick={() => { setSearch(''); setRoleFilter('all'); }}
            className="text-[13px] text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 transition-colors ml-auto"
          >
            Clear filters
          </button>
        )}
      </div>

      {!loading && error ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
            <X className="w-6 h-6 text-red-500 dark:text-red-400" />
          </div>
          <p className="text-[16px] font-semibold text-[var(--text-1)]">Failed to load users</p>
          <p className="text-[14px] text-[var(--text-3)] mt-2 max-w-md">
            {error.includes('404') 
              ? "The backend API for fetching users is not yet implemented (GET /users)."
              : error}
          </p>
        </div>
      ) : !loading && users.length === 0 ? (
        isFiltering ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <SlidersHorizontal className="w-10 h-10 text-[var(--text-3)] mb-3" />
            <p className="text-[15px] font-medium">No results match your filters</p>
            <Button variant="ghost" size="sm" className="mt-4" onClick={() => { setSearch(''); setRoleFilter('all'); }}>
              Clear filters
            </Button>
          </div>
        ) : (
          <EmptyState
            icon={Users}
            title="No pending users yet"
            description="Once users tried to sign up, they will appear here. You can create a new user to get started."
            action={
              permissions.create_user ? (
                <Link href="/client/users/create">
                  <CreateButton>Create User</CreateButton>
                </Link>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          <DataTable columns={columns} data={users} isLoading={loading} />
          {data && data.total > data.page_size && (
            <Pagination page={page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          )}
        </>
      )}

      <UserEditDialog
        target={editTarget}
        form={editForm}
        onFormChange={setEditForm}
        roleOptions={roleFilterOptions}
        saving={saving}
        onClose={closeEdit}
        onSave={handleEditSave}
      />

      <UserDeleteDialog
        target={deleteTarget}
        deleting={deleting}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
      />
      </>
      )}
    </>
  )
}
