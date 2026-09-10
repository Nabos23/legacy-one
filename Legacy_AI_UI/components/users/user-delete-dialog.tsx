import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import type { UserPublic } from '@/types'

interface UserDeleteDialogProps {
  target: UserPublic | null
  deleting: boolean
  onClose: () => void
  onConfirm: () => void
}

export function UserDeleteDialog({ target, deleting, onClose, onConfirm }: UserDeleteDialogProps) {
  return (
    <Dialog
      open={!!target}
      onOpenChange={open => !open && onClose()}
      title="Delete User"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm} disabled={deleting}>Delete</Button>
        </div>
      }
    >
      <p className="text-[14px] text-[var(--text-2)]">
        Are you sure you want to delete <strong>{target?.name}</strong>? This cannot be undone.
      </p>
    </Dialog>
  )
}
