'use client'

import { useEffect, useState } from 'react'
import { Select } from '@/components/ui/select'
import { SlackInstallationsView } from '@/components/connector-apps/SlackInstallationsView'
import { useAuth } from '@/contexts/auth-context'
import { useOrganizations } from '@/hooks/use-organizations'

/** Admin sees every org's Slack installations, scoped to one org at a time
 * via a picker (backend/connector_apps/slack list endpoint is always
 * org-scoped, same as backend/widget's list endpoint) -- defaults to the
 * admin's own org. */
export default function AdminSlackAppPage() {
  const { user, permissions } = useAuth()
  const isSuperAdmin = !!permissions?.is_super_admin
  const { data: orgsData } = useOrganizations(1, undefined, 100)
  const [organizationId, setOrganizationId] = useState('')

  useEffect(() => {
    if (!organizationId && user?.organization_id) setOrganizationId(user.organization_id)
  }, [organizationId, user?.organization_id])

  return (
    <div>
      {isSuperAdmin && (
        <div className="mb-5 max-w-xs">
          <Select
            value={organizationId}
            onValueChange={setOrganizationId}
            options={(orgsData?.items ?? []).map(o => ({ value: o.id!, label: o.name }))}
            placeholder="Select an organization"
          />
        </div>
      )}
      {organizationId && <SlackInstallationsView organizationId={organizationId} />}
    </div>
  )
}
