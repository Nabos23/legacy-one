'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Users2, Edit2, Trash2, Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { PageHeader } from '@/components/ui/page-header'
import { DataTable, type Column } from '@/components/ui/data-table'
import { EmptyState } from '@/components/ui/empty-state'
import { Pagination } from '@/components/ui/pagination'
import { Dialog } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { useTeams } from '@/hooks/use-teams'
import { useToast } from '@/hooks/use-toast'
import { teamsApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { useAuth } from '@/contexts/auth-context'
import type { TeamPublic } from '@/types'

export default function TeamsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<TeamPublic | null>(null)
  const [deleting, setDeleting] = useState(false)

  const { permissions, user } = useAuth()
  const { toast } = useToast()

  const orgId = permissions.is_super_admin ? undefined : (user?.organization_id ?? undefined)
  const { data, loading, error, refetch } = useTeams(page, orgId, search)

  const teams = useMemo(() => data?.items ?? [], [data?.items])

  const handleDelete = async () => {
    if (!deleteTarget?.id) return
    setDeleting(true)
    try {
      await teamsApi.remove(deleteTarget.id)
      toast.success('Team deleted')
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete team')
    } finally {
      setDeleting(false)
    }
  }

  const columns: Column<TeamPublic>[] = [
    {
      key: 'name',
      header: 'Team Name',
      render: row => (
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[var(--surface-2)] flex items-center justify-center text-[var(--primary)] shrink-0">
            <Users2 className="w-4 h-4" />
          </div>
          <div>
            <Link
              href={`/client/teams/${row.id}/edit`}
              className="font-medium text-[13.5px] hover:text-[var(--primary)] transition-colors"
            >
              {row.name}
            </Link>
          </div>
        </div>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: row => (
        <span className="text-[13px] text-[var(--text-2)] max-w-xs truncate block">
          {row.description || '—'}
        </span>
      ),
    },
    {
      key: 'member_ids',
      header: 'Members',
      render: row => (
        <Badge variant="neutral">
          {row.member_ids?.length || 0} {row.member_ids?.length === 1 ? 'member' : 'members'}
        </Badge>
      ),
    },
    {
      key: 'permissions',
      header: 'Team Permissions',
      render: row => {
        const count = row.permissions?.length || 0
        return (
          <Badge variant={count > 0 ? 'primary' : 'neutral'}>
            <Shield className="w-3 h-3 mr-1 inline-block" />
            {count > 0 ? `${count} Granted` : 'Default'}
          </Badge>
        )
      },
    },
    {
      key: 'created_at',
      header: 'Created',
      render: row => (
        <span className="text-[13px] text-[var(--text-3)]">
          {formatDate(row.created_at)}
        </span>
      ),
    },
    ...(permissions.edit_team || permissions.delete_team
      ? [
          {
            key: 'actions',
            header: 'Actions',
            render: (row: TeamPublic) => (
              <div className="flex items-center gap-1">
                {permissions.edit_team && (
                  <Link href={`/client/teams/${row.id}/edit`}>
                    <Button variant="ghost" size="xs" title="Edit team">
                      <Edit2 className="w-3.5 h-3.5" />
                    </Button>
                  </Link>
                )}
                {permissions.delete_team && (
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => setDeleteTarget(row)}
                    title="Delete team"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-500" />
                  </Button>
                )}
              </div>
            ),
          },
        ]
      : []),
  ]

  return (
    <>
      <PageHeader
        title="Teams"
        description="Manage user groups, members, and team permissions within your organization"
        actions={
          permissions.create_team ? (
            <Link href="/client/teams/create">
              <CreateButton>Create Team</CreateButton>
            </Link>
          ) : undefined
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div className="flex-1 min-w-[240px] max-w-md">
          <SearchInput
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search teams by name or description…"
          />
        </div>
      </div>

      {error ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-[16px] font-semibold text-[var(--text-1)]">Failed to load teams</p>
          <p className="text-[14px] text-[var(--text-3)] mt-2 max-w-md">{error}</p>
        </div>
      ) : !loading && teams.length === 0 ? (
        <EmptyState
          icon={Users2}
          title={search ? 'No matching teams' : 'No teams created yet'}
          description={
            search
              ? `No teams matching "${search}". Try adjusting your query.`
              : 'Create your first team to group users and assign shared team permissions.'
          }
          action={
            permissions.create_team && !search ? (
              <Link href="/client/teams/create">
                <CreateButton>Create Team</CreateButton>
              </Link>
            ) : undefined
          }
        />
      ) : (
        <>
          <DataTable data={teams} columns={columns} isLoading={loading} />
          {data && data.total_pages > 1 && (
            <div className="mt-4 flex justify-end">
              <Pagination
                page={page}
                pageSize={10}
                total={data.total}
                onPageChange={setPage}
              />
            </div>
          )}
        </>
      )}

      {deleteTarget && (
        <Dialog
          open={true}
          onOpenChange={open => {
            if (!open) setDeleteTarget(null)
          }}
          title="Delete Team"
        >
          <div className="space-y-4">
            <p className="text-[13.5px] text-[var(--text-2)]">
              Are you sure you want to delete <span className="font-semibold text-[var(--text-1)]">{deleteTarget.name}</span>?
              Any agents or orchestrations assigned to this team will revert to organization-wide visibility.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setDeleteTarget(null)} disabled={deleting}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleDelete} disabled={deleting} className="bg-red-600 hover:bg-red-700 text-white">
                {deleting ? 'Deleting…' : 'Delete Team'}
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </>
  )
}
