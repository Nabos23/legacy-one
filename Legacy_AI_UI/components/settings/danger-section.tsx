import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SettingsCard, SettingsCardHeader } from './settings-card'
import { useAuth } from '@/contexts/auth-context'

/** Account deletion is admin-mediated (no self-serve delete endpoint), so this routes to a request instead of a fake destructive action. */
export function DangerSection({ requestEmail = 'admin@oneai.dev' }: { requestEmail?: string }) {
  const { user } = useAuth()

  return (
    <SettingsCard className="border-red-500/20">
      <SettingsCardHeader
        icon={AlertTriangle}
        title="Danger Zone"
        description="Irreversible actions for your account"
      />
      <div className="flex items-center justify-between p-4 rounded-xl bg-red-500/5 border border-red-500/20">
        <div>
          <p className="text-[13.5px] font-medium text-[var(--text-1)]">Delete account</p>
          <p className="text-[12px] text-[var(--text-3)] mt-0.5 max-w-md">
            Permanently removes your account and access. This is handled by an administrator
            to make sure any agents or data you own are reassigned first.
          </p>
        </div>
        <a
          href={`mailto:${requestEmail}?subject=Account%20deletion%20request&body=User:%20${user?.email}`}
          className="shrink-0"
        >
          <Button variant="danger" size="sm">
            Request deletion
          </Button>
        </a>
      </div>
    </SettingsCard>
  )
}
