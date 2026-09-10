'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { agentsApi } from '@/lib/api/agents'
import { useAuth } from '@/contexts/auth-context'
import { OrchestrationCanvas } from '@/components/orchestration/OrchestrationCanvas'
import type { AgentPublic, OrchestrationPublic } from '@/types'

export default function CreateOrchestrationPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [agents, setAgents] = useState<AgentPublic[]>([])

  useEffect(() => {
    if (!user?.organization_id) return
    agentsApi.listByOrg(user.organization_id, 1, 100).then(d => setAgents(d.items))
  }, [user])

  const handleSaved = (orch: OrchestrationPublic) => {
    router.push(`/client/orchestrations/${orch.id}`)
  }

  return (
    <div className="flex flex-col min-h-0 flex-1">
      <OrchestrationCanvas
        orgAgents={agents}
        orgId={user?.organization_id ?? ''}
        onBack={() => router.push('/client/orchestrations')}
        onSaved={handleSaved}
      />
    </div>
  )
}
