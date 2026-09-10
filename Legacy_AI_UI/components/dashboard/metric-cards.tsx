'use client'

import { Bot, Activity, Wrench, Database } from 'lucide-react'
import { StatsCard } from '@/components/ui/stats-card'
import { useAgents } from '@/hooks/use-agents'
import { useTools } from '@/hooks/use-tools'
import { useDbConnections } from '@/hooks/use-db-connections'
import { useTraceStats } from '@/hooks/use-tracing'

export function MetricCards() {
  const { data: agentsData } = useAgents(1)
  const { data: toolsData } = useTools(1)
  const { data: dbData } = useDbConnections(1)
  const { stats } = useTraceStats()

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
      <StatsCard
        label="Total Agents"
        value={agentsData?.total ?? 0}
        icon={Bot}
        color="primary"
        href="/client/agents"
      />
      <StatsCard
        label="Total Executions"
        value={stats?.total_traces ?? 0}
        icon={Activity}
        color="success"
        href="/client/tracing"
      />
      <StatsCard
        label="Total Tools"
        value={toolsData?.total ?? 0}
        icon={Wrench}
        color="info"
        href="/client/tools"
      />
      <StatsCard
        label="DB Connections"
        value={dbData?.total ?? 0}
        icon={Database}
        color="warning"
        href="/client/db-connections"
      />
    </div>
  )
}
