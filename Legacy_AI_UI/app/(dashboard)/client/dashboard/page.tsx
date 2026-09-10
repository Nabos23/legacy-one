'use client'


import Link from 'next/link'
import { CreateButton } from '@/components/ui/create-button'
import { PageHeader } from '@/components/ui/page-header'
import { MetricCards } from '@/components/dashboard/metric-cards'
import { AgentAnalyticsChart } from '@/components/dashboard/agent-analytics-chart'
import { AgentExecutionStatus } from '@/components/dashboard/agent-execution-status'
import { TaskCompletionChart } from '@/components/dashboard/task-completion-chart'
import { SystemAlertsCard } from '@/components/dashboard/system-alerts-card'
import { ComputeTracker } from '@/components/dashboard/compute-tracker'
import { AgentListCard } from '@/components/dashboard/agent-list-card'
import { useAuth } from '@/contexts/auth-context'
import { useGreeting } from '@/hooks/use-greeting'

export default function ClientDashboardPage() {
  const { user } = useAuth()
  const greeting = useGreeting()
  return (
    <>
      <PageHeader
        title={`${greeting}, ${user?.name ?? 'there'} 👋`}
        description="Here's what's happening with your agents today."
        actions={
          <Link href="/client/agents/create">
            <CreateButton>New Agent</CreateButton>
          </Link>
        }
      />

      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-12 animate-slideUpFade" style={{ animationDelay: '0ms' }}>
          <MetricCards />
        </div>

        {/* Row 2 */}
        <div className="col-span-12 lg:col-span-8 animate-slideUpFade" style={{ animationDelay: '50ms' }}>
          <AgentAnalyticsChart />
        </div>
        <div className="col-span-12 lg:col-span-4 animate-slideUpFade" style={{ animationDelay: '100ms' }}>
          <AgentExecutionStatus />
        </div>

        {/* Row 3 */}
        <div className="col-span-12 md:col-span-6 lg:col-span-4 animate-slideUpFade" style={{ animationDelay: '150ms' }}>
          <TaskCompletionChart />
        </div>
        <div className="col-span-12 md:col-span-6 lg:col-span-4 animate-slideUpFade" style={{ animationDelay: '200ms' }}>
          <SystemAlertsCard />
        </div>
        <div className="col-span-12 md:col-span-6 lg:col-span-4 animate-slideUpFade" style={{ animationDelay: '250ms' }}>
          <ComputeTracker />
        </div>

        {/* Row 4 */}
        <div className="col-span-12 animate-slideUpFade" style={{ animationDelay: '300ms' }}>
          <AgentListCard />
        </div>
      </div>
    </>
  )
}
