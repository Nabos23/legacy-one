'use client'

import { useMemo } from 'react'
import { TrendingUp, Timer, DollarSign, Activity } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useRecentTraces, useTraceStats } from '@/hooks/use-tracing'

const SLOW_MS = 2000

export function SystemAlertsCard() {
  const { stats } = useTraceStats()
  const { traces } = useRecentTraces()

  const insights = useMemo(() => {
    const items: { icon: typeof Activity; tone: 'primary' | 'warning' | 'success'; title: string; sub: string }[] = []

    const topAgent = (stats?.agent_breakdown ?? []).slice().sort((a, b) => b.trace_count - a.trace_count)[0]
    if (topAgent) {
      items.push({
        icon: TrendingUp,
        tone: 'primary',
        title: `Top agent: ${topAgent.agent_name}`,
        sub: `${topAgent.trace_count} executions · ${topAgent.total_tokens.toLocaleString()} tokens`,
      })
    }

    const slow = traces.filter(t => (t.latency ?? 0) > SLOW_MS).length
    if (slow > 0) {
      items.push({
        icon: Timer,
        tone: 'warning',
        title: `${slow} slow execution${slow === 1 ? '' : 's'}`,
        sub: `Latency over ${SLOW_MS / 1000}s — consider reviewing prompts or tools`,
      })
    }

    if (stats?.total_cost != null) {
      items.push({
        icon: DollarSign,
        tone: 'success',
        title: `$${stats.total_cost.toFixed(4)} spent`,
        sub: `${stats.total_traces} executions · ${(stats.total_input_tokens + stats.total_output_tokens).toLocaleString()} tokens total`,
      })
    }

    return items
  }, [stats, traces])

  const toneStyles: Record<string, string> = {
    primary: 'bg-violet-50 dark:bg-violet-950/30 border-violet-200/60 dark:border-violet-800/40 border-l-violet-500',
    warning: 'bg-amber-50 dark:bg-amber-950/20 border-amber-200/60 dark:border-amber-800/40 border-l-amber-500',
    success: 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200/60 dark:border-emerald-800/40 border-l-emerald-500',
  }
  const iconStyles: Record<string, string> = {
    primary: 'bg-violet-100 dark:bg-violet-900/50 text-violet-600 dark:text-violet-400',
    warning: 'bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400',
    success: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400',
  }

  return (
    <div className="card-1 p-5 rounded-[var(--radius-lg)] flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[15px] font-bold text-[var(--text-1)]">Insights</h3>
        {insights.length > 0 && <Badge variant="primary">{insights.length}</Badge>}
      </div>

      <div className="flex flex-col gap-2.5">
        {insights.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Activity className="w-6 h-6 text-[var(--text-3)] mb-2" />
            <p className="text-[13px] text-[var(--text-3)]">No insights yet. Run an agent to see activity.</p>
          </div>
        ) : (
          insights.map((it, i) => {
            const Icon = it.icon
            return (
              <div key={i} className={`rounded-xl p-3.5 border border-l-[3px] ${toneStyles[it.tone]}`}>
                <div className="flex items-start gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${iconStyles[it.tone]}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-semibold text-[var(--text-1)] truncate">{it.title}</p>
                    <p className="text-[12px] text-[var(--text-3)] mt-0.5">{it.sub}</p>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
