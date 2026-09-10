'use client'

import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { useTracing } from '@/hooks/use-tracing'
import { AgentAvatar } from '@/components/dashboard/agent-avatar'

function LatencyBadge({ ms }: { ms?: number }) {
  if (ms == null) return <Badge variant="neutral">done</Badge>
  const variant = ms < 500 ? 'success' : ms < 2000 ? 'warning' : 'danger'
  return <Badge variant={variant}>{ms}ms</Badge>
}

export function AgentExecutionStatus() {
  const { data, loading } = useTracing(1)
  const traces = (data?.items ?? []).slice(0, 5)

  return (
    <div className="card-1 p-5 rounded-[var(--radius-lg)]">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[15px] font-bold text-[var(--text-1)]">Recent Executions</h3>
        <Link href="/client/tracing" className="text-[12px] text-violet-600 dark:text-violet-400 hover:text-violet-500 dark:hover:text-violet-300 font-medium transition-colors">
          View all →
        </Link>
      </div>

      <div className="space-y-3">
        {loading ? (
          <p className="text-[13px] text-[var(--text-3)] py-6 text-center">Loading…</p>
        ) : traces.length === 0 ? (
          <p className="text-[13px] text-[var(--text-3)] py-6 text-center">No executions yet.</p>
        ) : (
          traces.map(trace => {
            const name = trace.agent_name || 'Agent'
            return (
              <div key={trace.id} className="flex items-center gap-3 py-2">
                <AgentAvatar name={name} size="sm" />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium truncate">{name}</p>
                </div>
                <LatencyBadge ms={trace.latency} />
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
