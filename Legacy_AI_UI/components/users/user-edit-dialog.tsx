import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import type { AssignableRole, UserPublic } from '@/types'

interface UserEditDialogProps {
  target: UserPublic | null
  form: { name: string; role: string }
  onFormChange: (form: { name: string; role: string }) => void
  roleOptions: AssignableRole[]
  saving: boolean
  onClose: () => void
  onSave: () => void
}

export function UserEditDialog({ target, form, onFormChange, roleOptions, saving, onClose, onSave }: UserEditDialogProps) {
  return (
    <Dialog
      open={!!target}
      onOpenChange={open => !open && onClose()}
      title="Edit User"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={onSave} disabled={saving}>Save</Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="text-[13px] font-medium block mb-2">Full Name</label>
          <Input
            value={form.name}
            onChange={e => onFormChange({ ...form, name: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[13px] font-medium block mb-2">Role</label>
          <Select
            value={form.role}
            onValueChange={v => onFormChange({ ...form, role: v })}
            options={roleOptions.map(r => ({ value: r.name, label: r.label }))}
          />
        </div>
      </div>
    </Dialog>
  )
}
