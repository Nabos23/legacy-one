'use client'

import { useState } from 'react'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchInput } from '@/components/ui/search-input'
import { Textarea } from '@/components/ui/textarea'
import { useUsers } from '@/hooks/use-users'
import { useToast } from '@/hooks/use-toast'
import { teamsApi } from '@/lib/api'

interface TeamCreateDialogProps {
  open: boolean
  orgId?: string
  onClose: () => void
  onCreated: () => void
}

export function TeamCreateDialog({ open, orgId, onClose, onCreated }: TeamCreateDialogProps) {
  const { toast } = useToast()
  const { data: usersData } = useUsers(1, orgId, undefined, undefined, 100, {}, open)
  const orgUsers = usersData?.items ?? []

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [memberIds, setMemberIds] = useState<string[]>([])
  const [memberSearch, setMemberSearch] = useState('')
  const [saving, setSaving] = useState(false)

  const reset = () => {
    setName('')
    setDescription('')
    setMemberIds([])
    setMemberSearch('')
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const filteredUsers = orgUsers.filter(u => {
    const q = memberSearch.toLowerCase()
    return !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
  })

  const handleCreate = async () => {
    if (!name.trim() || !orgId) return
    setSaving(true)
    try {
      await teamsApi.create({
        organization_id: orgId,
        name: name.trim(),
        description: description.trim() || undefined,
        member_ids: memberIds,
      })
      toast.success('Team created')
      reset()
      onCreated()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create team')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={o => !o && handleClose()}
      title="Create Team"
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={handleClose}>Cancel</Button>
          <Button variant="primary" onClick={handleCreate} disabled={saving || !name.trim()}>
            Create Team
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="text-[13px] font-medium block mb-2">Team Name</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Sales, Support, Engineering" />
        </div>
        <div>
          <label className="text-[13px] font-medium block mb-2">Description</label>
          <Textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="What does this team do?"
          />
        </div>
        <div>
          <label className="text-[13px] font-medium block mb-2">
            Members ({memberIds.length} selected)
          </label>
          <SearchInput
            value={memberSearch}
            onChange={e => setMemberSearch(e.target.value)}
            placeholder="Search users..."
            className="mb-2"
          />
          <div className="max-h-48 overflow-y-auto space-y-1 border border-[var(--border)] rounded-[var(--radius-md)] p-2">
            {filteredUsers.length === 0 ? (
              <p className="text-[12px] text-[var(--text-3)] p-2">No users found in this organization.</p>
            ) : (
              filteredUsers.map(u => {
                const selected = memberIds.includes(u.id!)
                return (
                  <label key={u.id} className="flex items-center gap-2 p-2 rounded-[var(--radius-sm)] cursor-pointer hover:bg-[var(--surface-2)]">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() =>
                        setMemberIds(prev => (selected ? prev.filter(id => id !== u.id) : [...prev, u.id!]))
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
