import { useMemo, useState } from 'react'
import { Pencil, Trash2, Users2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CreateButton } from '@/components/ui/create-button'
import { SearchInput } from '@/components/ui/search-input'
import { DataTable, type Column } from '@/components/ui/data-table'
import { Pagination } from '@/components/ui/pagination'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { EmptyState } from '@/components/ui/empty-state'
import { TeamCreateDialog } from '@/components/teams/team-create-dialog'
import { TeamMembersDialog } from '@/components/teams/team-members-dialog'
import { TeamDeleteDialog } from '@/components/teams/team-delete-dialog'
import { useTeams } from '@/hooks/use-teams'
import { useUsers } from '@/hooks/use-users'
import { useToast } from '@/hooks/use-toast'
import { useAuth } from '@/contexts/auth-context'
import { formatDate } from '@/lib/utils'
import { teamsApi } from '@/lib/api'
import type { TeamPublic, UserPublic } from '@/types'

interface TeamsPanelProps {
  orgId?: string
}

export function TeamsPanel({ orgId }: TeamsPanelProps) {
  const { permissions } = useAuth()
  const { toast } = useToast()
  const { data, loading, error, page, setPage, refetch } = useTeams(1, orgId)
  const { data: usersData } = useUsers(1, orgId, undefined, undefined, 1000)

  const userMap = useMemo(() => {
    const map = new Map<string, UserPublic>()
    for (const u of usersData?.items ?? []) {
      if (u.id) map.set(u.id, u)
    }
    return map
  }, [usersData?.items])

  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [membersTarget, setMembersTarget] = useState<TeamPublic | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<TeamPublic | null>(null)
  const [deleting, setDeleting] = useState(false)

  const teams = useMemo(() => {
    const items = data?.items ?? []
    const q = search.toLowerCase()
    if (!q) return items
    return items.filter(
      t => t.name.toLowerCase().includes(q) || (t.description ?? '').toLowerCase().includes(q)
    )
  }, [data?.items, search])

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
      header: 'Name',
      render: row => <span className="font-medium">{row.name}</span>,
    },
    {
      key: 'description',
      header: 'Description',
      render: row => (
        <span className="text-[13px] text-[var(--text-2)]">{row.description || '—'}</span>
      ),
    },
    {
      key: 'member_ids',
      header: 'Members',
      render: row => {
        const memberIds = row.member_ids ?? []
        if (memberIds.length === 0) {
          return <Badge variant="neutral">0 members</Badge>
        }

        const options = memberIds.map(id => {
          const u = userMap.get(id)
          return {
            value: id,
            label: u ? `${u.name} (${u.email})` : `User (${id.slice(-6)})`,
          }
        })

        return (
          <div className="w-48">
            <Select
              value=""
              onValueChange={() => {}}
              placeholder={`${memberIds.length} ${memberIds.length === 1 ? 'member' : 'members'}`}
              options={options}
            />
          </div>
        )
      },
    },
    {
      key: 'created_at',
      header: 'Created',
      render: row => <span className="text-[13px] text-[var(--text-3)]">{formatDate(row.created_at)}</span>,
    },
    ...(permissions.edit_team || permissions.delete_team
      ? [
          {
            key: 'actions',
            header: 'Actions',
            render: (row: TeamPublic) => (
              <div className="flex items-center gap-2">
                {permissions.edit_team && (
                  <Button variant="ghost" size="xs" onClick={() => setMembersTarget(row)} title="Manage members">
                    <Pencil className="w-4 h-4 text-foreground hover:text-violet-600" />
                  </Button>
                )}
                {permissions.delete_team && (
                  <Button variant="ghost" size="xs" onClick={() => setDeleteTarget(row)} title="Delete team">
                    <Trash2 className="w-4 h-4 text-red-500 hover:text-red-600 dark:text-red-400" />
                  </Button>
                )}
              </div>
            ),
          } as Column<TeamPublic>,
        ]
      : []),
  ]

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <SearchInput
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search teams..."
          className="max-w-[280px]"
        />

        {permissions.create_team && (
          <CreateButton className="ml-auto" onClick={() => setCreateOpen(true)}>
            Create Team
          </CreateButton>
        )}
      </div>

      {!loading && error ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
            <X className="w-6 h-6 text-red-500 dark:text-red-400" />
          </div>
          <p className="text-[16px] font-semibold text-[var(--text-1)]">Failed to load teams</p>
          <p className="text-[14px] text-[var(--text-3)] mt-2 max-w-md">{error}</p>
        </div>
      ) : !loading && teams.length === 0 && !search ? (
        <EmptyState
          icon={Users2}
          title="No teams yet"
          description="Create your first team to start grouping users and assigning agents to them."
          action={
            permissions.create_team ? (
              <CreateButton onClick={() => setCreateOpen(true)}>Create Team</CreateButton>
            ) : undefined
          }
        />
      ) : (
        <>
          <DataTable columns={columns} data={teams} isLoading={loading} />
          {data && data.total > data.page_size && (
            <Pagination page={page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
          )}
        </>
      )}

      <TeamCreateDialog
        open={createOpen}
        orgId={orgId}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false)
          refetch()
        }}
      />

      <TeamMembersDialog
        team={membersTarget}
        orgId={orgId}
        onClose={() => setMembersTarget(null)}
        onChanged={async () => {
          await refetch()
          if (membersTarget?.id) {
            const updated = await teamsApi.get(membersTarget.id)
            setMembersTarget(updated)
          }
        }}
      />

      <TeamDeleteDialog
        target={deleteTarget}
        deleting={deleting}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
      />
    </>
  )
}
