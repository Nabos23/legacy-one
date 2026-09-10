'use client'

import { useState, useEffect, useMemo } from 'react'
import { X, SlidersHorizontal, Users, Edit2, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { Select } from '@/components/ui/select'
import { PageHeader } from '@/components/ui/page-header'
import { DataTable, type Column, type SortState } from '@/components/ui/data-table'
import { BulkDeleteButton } from '@/components/ui/bulk-delete-button'
import { Pagination } from '@/components/ui/pagination'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { UserEditDialog } from '@/components/users/user-edit-dialog'
import { UserDeleteDialog } from '@/components/users/user-delete-dialog'
import { useUsers } from '@/hooks/use-users'
import { useOrganizations } from '@/hooks/use-organizations'
import { useUserEditDelete } from '@/hooks/use-user-edit-delete'
import { useBulkDelete } from '@/hooks/use-bulk-delete'
import { useToast } from '@/hooks/use-toast'
import { formatDate, avatarColor, normalizeRoleName } from '@/lib/utils'
import { useAuth } from '@/contexts/auth-context'
import { authApi, usersApi } from '@/lib/api'
import type { UserPublic, AssignableRole } from '@/types'

export default function UsersPage() {
  const { permissions, user } = useAuth()

  // super_admin → global /users list, optionally narrowed to one org via the
  // filter dropdown below; everyone else → org-scoped /organizations/{id}/users.
  const [orgFilter, setOrgFilter] = useState('')
  const orgId = permissions.is_super_admin ? (orgFilter || undefined) : (user?.organization_id ?? undefined)

  const { data: orgsData } = useOrganizations(1, undefined, 1000)
  const orgNameMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const org of orgsData?.items ?? []) {
      if (org.id) map[org.id] = org.name
    }
    return map
  }, [orgsData?.items])

  const [roleOptions, setRoleOptions] = useState<AssignableRole[]>([])
  useEffect(() => {
    authApi.assignableRoles().then(setRoleOptions).catch(() => setRoleOptions([]))
  }, [])

  const [allRoles, setAllRoles] = useState<AssignableRole[]>([])
  useEffect(() => {
    authApi.allRoles().then(setAllRoles).catch(() => setAllRoles([]))
  }, [])

  const adminRoleNames = useMemo(
    () => new Set(allRoles.filter(r => r.is_admin).map(r => normalizeRoleName(r.name))),
    [allRoles],
  )

  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [pageSize, setPageSize] = useState(10)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const [sort, setSort] = useState<SortState>(null)
  const { data, loading, error, page, setPage, refetch } = useUsers(
    1,
    orgId,
    debouncedSearch,
    roleFilter === 'all' ? undefined : roleFilter,
    pageSize,
    { sortBy: (sort?.key as 'name' | 'email' | 'created_at') ?? undefined, sortOrder: sort?.dir },
  )

  // Search (name/email) and role are applied server-side, so the returned page
  // is already the filtered result — pagination totals stay accurate.
  const users = data?.items ?? []

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  const handleRoleChange = (val: string) => {
    setRoleFilter(val)
    setPage(1)
  }

  const {
    editTarget, editForm, setEditForm, saving, openEdit, handleEditSave, closeEdit,
    deleteTarget, deleting, setDeleteTarget, handleDelete,
  } = useUserEditDelete(refetch)

  const { toast } = useToast()
  const [bulkDeleteTarget, setBulkDeleteTarget] = useState<{ ids: string[]; clear: () => void } | null>(null)
  const bulkDelete = useBulkDelete(id => usersApi.remove(id), { entity: 'user', onDone: refetch })

  const handleBulkDeleteRequest = (ids: string[], clear: () => void) => {
    // Never let a bulk selection include the caller's own account — the API
    // would reject it anyway, but this avoids a spurious "1 failed" toast.
    const targetIds = ids.filter(id => id !== user?.id)
    if (targetIds.length === 0) {
      toast.error("You can't delete your own account.")
      return
    }
    setBulkDeleteTarget({ ids: targetIds, clear })
  }

  const handleBulkDelete = async () => {
    if (!bulkDeleteTarget) return
    try {
      await bulkDelete.run(bulkDeleteTarget.ids, bulkDeleteTarget.clear)
    } finally {
      setBulkDeleteTarget(null)
    }
  }

  const baseColumns: Column<UserPublic>[] = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      sortAccessor: row => row.name,
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
      sortable: true,
      sortAccessor: row => row.email,
      render: row => <span className="text-[13px] text-[var(--text-2)]">{row.email}</span>,
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
  ]

  if (permissions.is_super_admin) {
    baseColumns.push({
      key: 'organization_id',
      header: 'Organization',
      render: row => (
        <span className="text-[13px] text-[var(--text-2)]">
          {orgNameMap[row.organization_id] ?? row.organization_id.slice(-8)}
        </span>
      ),
    })
  }

  baseColumns.push({
    key: 'created_at',
    header: 'Joined',
    sortable: true,
    sortAccessor: row => row.created_at ?? '',
    render: row => <span className="text-[13px] text-[var(--text-3)]">{formatDate(row.created_at)}</span>,
  })

  if (permissions.edit_user || permissions.delete_user) {
    baseColumns.push({
      key: 'actions',
      header: 'Actions',
      render: row => (
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
      ),
    })
  }

  const columns = baseColumns

  const isFiltering = !!search.trim() || roleFilter !== 'all' || !!orgFilter

  const resetFilters = () => {
    setSearch('')
    setRoleFilter('all')
    setOrgFilter('')
    setPage(1)
  }

  return (
    <>
      <PageHeader
        title="Users"
        description="Manage system users and permissions"
        actions={
          permissions.create_user ? (
            <Link href="/admin/users/create">
              <CreateButton>Create User</CreateButton>
            </Link>
          ) : undefined
        }
      />

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
            ...roleOptions.map(r => ({ value: r.name, label: r.label })),
          ]}
        />

        {permissions.is_super_admin && (
          <Select
            value={orgFilter}
            onValueChange={v => { setOrgFilter(v); setPage(1) }}
            className="w-[200px]"
            options={[
              { value: '', label: 'All organizations' },
              ...(orgsData?.items ?? []).map(o => ({ value: o.id!, label: o.name })),
            ]}
          />
        )}

        {isFiltering && data && (
          <span className="text-[13px] text-[var(--text-3)]">
            <strong className="text-[var(--text-1)]">{data.total}</strong> result{data.total !== 1 ? 's' : ''}
          </span>
        )}

        {isFiltering && (
          <button
            onClick={resetFilters}
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
            {error}
          </p>
        </div>
      ) : !loading && users.length === 0 ? (
        isFiltering ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <SlidersHorizontal className="w-10 h-10 text-[var(--text-3)] mb-3" />
            <p className="text-[15px] font-medium">No users match your filters</p>
            <Button variant="ghost" size="sm" className="mt-4" onClick={resetFilters}>
              Clear filters
            </Button>
          </div>
        ) : (
          <EmptyState
            icon={Users}
            title="No users yet"
            description="Create your first user to get started"
            action={
              permissions.create_user ? (
                <Link href="/admin/users/create">
                  <CreateButton>Create User</CreateButton>
                </Link>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          <DataTable
            columns={columns}
            data={users}
            isLoading={loading}
            sortState={sort}
            onSortChange={next => { setSort(next); setPage(1) }}
            {...(permissions.delete_user ? {
              getRowId: (row: UserPublic) => row.id!,
              bulkActions: ({ ids, clear }: { ids: string[]; clear: () => void }) => (
                <BulkDeleteButton count={ids.length} busy={bulkDelete.busy} onClick={() => handleBulkDeleteRequest(ids, clear)} />
              ),
            } : {})}
          />
          {data && data.total > pageSize && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.total}
              onPageChange={setPage}
              onPageSizeChange={s => { setPageSize(s); setPage(1) }}
            />
          )}
        </>
      )}

      <UserEditDialog
        target={editTarget}
        form={editForm}
        onFormChange={setEditForm}
        roleOptions={roleOptions}
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

      <Dialog
        open={!!bulkDeleteTarget}
        onOpenChange={open => !open && setBulkDeleteTarget(null)}
        title="Delete Users"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setBulkDeleteTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleBulkDelete} disabled={bulkDelete.busy}>
              {bulkDelete.busy ? 'Deleting…' : 'Delete'}
            </Button>
          </div>
        }
      >
        <p className="text-[14px] text-[var(--text-2)]">
          Delete the <strong>{bulkDeleteTarget?.ids.length}</strong> selected user{bulkDeleteTarget?.ids.length === 1 ? '' : 's'}? This cannot be undone.
        </p>
      </Dialog>
    </>
  )
}
