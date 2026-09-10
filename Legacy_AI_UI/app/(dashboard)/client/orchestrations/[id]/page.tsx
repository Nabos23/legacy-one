'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { agentsApi } from '@/lib/api/agents'
import { orchestrationsApi } from '@/lib/api/orchestrations'
import { useAuth } from '@/contexts/auth-context'
import { useToast } from '@/hooks/use-toast'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import { OrchestrationCanvas } from '@/components/orchestration/OrchestrationCanvas'
import type { AgentPublic, OrchestrationPublic } from '@/types'

export default function OrchestrationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const { user } = useAuth()
  const { toast } = useToast()

  const [orch, setOrch] = useState<OrchestrationPublic | null>(null)
  useBreadcrumbLabel(id, orch?.name)
  const [agents, setAgents] = useState<AgentPublic[]>([])

  useEffect(() => {
    orchestrationsApi.get(id).then(setOrch).catch(() => toast.error('Failed to load orchestration'))
    if (user?.organization_id) {
      agentsApi.listByOrg(user.organization_id, 1, 100).then(d => setAgents(d.items))
    }
  }, [id, user])

  if (!orch) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-0 flex-1">
      <OrchestrationCanvas
        orchestrationId={id}
        initialOrch={orch}
        orgAgents={agents}
        orgId={user?.organization_id ?? ''}
        onBack={() => router.push('/client/orchestrations')}
        onSaved={updated => setOrch(updated)}
        onChat={() => router.push(`/client/orchestrations/${id}/chat`)}
      />
    </div>
  )
}
