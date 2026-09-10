'use client'

import { SlackInstallationsView } from '@/components/connector-apps/SlackInstallationsView'
import { useAuth } from '@/contexts/auth-context'

export default function ClientSlackAppPage() {
  const { user } = useAuth()
  if (!user?.organization_id) return null
  return <SlackInstallationsView organizationId={user.organization_id} />
}
