'use client'

import { useEffect, useMemo, useState } from 'react'
import { X } from 'lucide-react'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { useUsers } from '@/hooks/use-users'
import { useToast } from '@/hooks/use-toast'
import { teamsApi } from '@/lib/api'
import type { TeamPublic } from '@/types'

interface TeamMembersDialogProps {
  team: TeamPublic | null
  orgId?: string
  onClose: () => void
  onChanged: () => void
}

export function TeamMembersDialog({ team, orgId, onClose, onChanged }: TeamMembersDialogProps) {
  const { toast } = useToast()
  const { data: usersData } = useUsers(1, orgId, undefined, undefined, 100, {}, !!team)
  const orgUsers = usersData?.items ?? []

  const [search, setSearch] = useState('')
  const [toAdd, setToAdd] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  useEffect(() => {
    setName(team?.name ?? '')
    setDescription(team?.description ?? '')
  }, [team?.id])

  const detailsChanged = team && (name !== team.name || description !== (team.description ?? ''))

  const handleSaveDetails = async () => {
    if (!team?.id || !name.trim()) return
    setBusy(true)
    try {
      await teamsApi.update(team.id, { name: name.trim(), description: description.trim() || undefined })
      toast.success('Team updated')
      onChanged()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update team')
    } finally {
      setBusy(false)
    }
  }

  const userMap = useMemo(() => {
    const map: Record<string, { name: string; email: string }> = {}
    for (const u of orgUsers) if (u.id) map[u.id] = { name: u.name, email: u.email }
    return map
  }, [orgUsers])

  const memberIds = team?.member_ids ?? []
  const candidates = orgUsers.filter(u => !memberIds.includes(u.id!))
  const filteredCandidates = candidates.filter(u => {
    const q = search.toLowerCase()
    return !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
  })

  const handleClose = () => {
    setSearch('')
    setToAdd([])
    onClose()
  }

  const handleAdd = async () => {
    if (!team?.id || toAdd.length === 0) return
    setBusy(true)
    try {
      await teamsApi.addMembers(team.id, toAdd)
      toast.success('Members added')
      setToAdd([])
      onChanged()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add members')
    } finally {
      setBusy(false)
    }
  }

  const handleRemove = async (userId: string) => {
    if (!team?.id) return
    setBusy(true)
    try {
      await teamsApi.removeMember(team.id, userId)
      toast.success('Member removed')
      onChanged()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove member')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={!!team}
      onOpenChange={o => !o && handleClose()}
      title={team ? `Manage Members — ${team.name}` : 'Manage Members'}
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={handleClose}>Close</Button>
          <Button variant="primary" onClick={handleAdd} disabled={busy || toAdd.length === 0}>
            Add {toAdd.length > 0 ? `(${toAdd.length})` : ''}
          </Button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-3 items-end">
          <div className="space-y-3">
            <div>
              <label className="text-[13px] font-medium block mb-2">Team Name</label>
              <Input value={name} onChange={e => setName(e.target.value)} />
            </div>
            <div>
              <label className="text-[13px] font-medium block mb-2">Description</label>
              <Textarea value={description} onChange={e => setDescription(e.target.value)} />
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={handleSaveDetails} disabled={busy || !detailsChanged || !name.trim()}>
            Save
          </Button>
        </div>

        <div>
          <label className="text-[13px] font-medium block mb-2">
            Current members ({memberIds.length})
          </label>
          <div className="max-h-40 overflow-y-auto space-y-1 border border-[var(--border)] rounded-[var(--radius-md)] p-2">
            {memberIds.length === 0 ? (
              <p className="text-[12px] text-[var(--text-3)] p-2">No members yet.</p>
            ) : (
              memberIds.map(id => (
                <div key={id} className="flex items-center justify-between gap-2 p-2 rounded-[var(--radius-sm)] hover:bg-[var(--surface-2)]">
                  <div className="min-w-0">
                    <span className="text-[13px]">{userMap[id]?.name ?? id}</span>
                    {userMap[id]?.email && (
                      <span className="text-[12px] text-[var(--text-3)] ml-2">{userMap[id].email}</span>
                    )}
                  </div>
                  <Button variant="ghost" size="xs" onClick={() => handleRemove(id)} disabled={busy} title="Remove">
                    <X className="w-3.5 h-3.5 text-red-500 dark:text-red-400" />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>

        <div>
          <label className="text-[13px] font-medium block mb-2">Add members</label>
          <SearchInput
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search users..."
            className="mb-2"
          />
          <div className="max-h-48 overflow-y-auto space-y-1 border border-[var(--border)] rounded-[var(--radius-md)] p-2">
            {filteredCandidates.length === 0 ? (
              <p className="text-[12px] text-[var(--text-3)] p-2">No other users available to add.</p>
            ) : (
              filteredCandidates.map(u => {
                const selected = toAdd.includes(u.id!)
                return (
                  <label key={u.id} className="flex items-center gap-2 p-2 rounded-[var(--radius-sm)] cursor-pointer hover:bg-[var(--surface-2)]">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() =>
                        setToAdd(prev => (selected ? prev.filter(id => id !== u.id) : [...prev, u.id!]))
                      }
                      className="w-4 h-4 accent-violet-600"
                    />
                    <span className="text-[13px]">{u.name}</span>
                    <span className="text-[12px] text-[var(--text-3)]">{u.email}</span>
                  </label>
                )
              })
            )}
          </div>
        </div>
      </div>
    </Dialog>
  )
}
