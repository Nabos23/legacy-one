import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import type { TeamPublic } from '@/types'

interface TeamDeleteDialogProps {
  target: TeamPublic | null
  deleting: boolean
  onClose: () => void
  onConfirm: () => void
}

export function TeamDeleteDialog({ target, deleting, onClose, onConfirm }: TeamDeleteDialogProps) {
  return (
    <Dialog
      open={!!target}
      onOpenChange={open => !open && onClose()}
      title="Delete Team"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm} disabled={deleting}>Delete</Button>
        </div>
      }
    >
      <p className="text-[14px] text-[var(--text-2)]">
        Are you sure you want to delete <strong>{target?.name}</strong>? Any agent assigned to this team
        will revert to organization-wide visibility. This cannot be undone.
      </p>
    </Dialog>
  )
}
