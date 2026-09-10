'use client'

import { useState } from 'react'
import { usersApi } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'
import type { UserPublic } from '@/types'

/**
 * Shared edit/delete state + handlers for user list pages (admin and client),
 * which otherwise duplicate this logic identically.
 */
export function useUserEditDelete(onSuccess: () => void) {
  const { toast } = useToast()

  const [editTarget, setEditTarget] = useState<UserPublic | null>(null)
  const [editForm, setEditForm] = useState({ name: '', role: '' })
  const [saving, setSaving] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState<UserPublic | null>(null)
  const [deleting, setDeleting] = useState(false)

  const openEdit = (row: UserPublic) => {
    setEditTarget(row)
    setEditForm({ name: row.name, role: row.role })
  }

  const handleEditSave = async () => {
    if (!editTarget) return
    setSaving(true)
    try {
      await usersApi.update(editTarget.id!, { name: editForm.name, role: editForm.role })
      toast.success('User updated')
      setEditTarget(null)
      onSuccess()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update user')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await usersApi.remove(deleteTarget.id!)
      toast.success('User removed')
      setDeleteTarget(null)
      onSuccess()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove user')
    } finally {
      setDeleting(false)
    }
  }

  return {
    editTarget,
    editForm,
    setEditForm,
    saving,
    openEdit,
    handleEditSave,
    closeEdit: () => setEditTarget(null),
    deleteTarget,
    deleting,
    setDeleteTarget,
    handleDelete,
  }
}
