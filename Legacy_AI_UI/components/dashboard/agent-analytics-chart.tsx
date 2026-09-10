'use client'

import { useMemo, useState } from 'react'
import dynamic from 'next/dynamic'
import { useTheme } from '@/contexts/theme-context'
import { useRecentTraces } from '@/hooks/use-tracing'

const AgentActivityArea = dynamic(() => import('./charts/agent-activity-area'), {
  ssr: false,
  loading: () => <div className="h-[220px]" />,
})

const PERIOD_DAYS: Record<'7D' | '30D' | '90D', number> = { '7D': 7, '30D': 30, '90D': 90 }

export function AgentAnalyticsChart() {
  const [period, setPeriod] = useState<'7D' | '30D' | '90D'>('7D')
  const { traces } = useRecentTraces()
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const data = useMemo(() => {
    const days = PERIOD_DAYS[period]
    // Build an ordered bucket per day for the last `days` days
    const buckets = new Map<string, { executions: number; cost: number }>()
    const labels: string[] = []
    const now = new Date()
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(now.getDate() - i)
      const key = `${d.getMonth() + 1}/${d.getDate()}`
      labels.push(key)
      buckets.set(key, { executions: 0, cost: 0 })
    }
    for (const t of traces) {
      if (!t.timestamp) continue
      const d = new Date(t.timestamp)
      if (Number.isNaN(d.getTime())) continue
      const key = `${d.getMonth() + 1}/${d.getDate()}`
      const b = buckets.get(key)
      if (b) {
        b.executions += 1
        b.cost += t.total_cost ?? 0
      }
    }
    return labels.map(name => ({
      name,
      executions: buckets.get(name)!.executions,
      cost: Number(buckets.get(name)!.cost.toFixed(4)),
    }))
  }, [traces, period])

  const hasData = data.some(d => d.executions > 0)

  return (
    <div className="card-1 p-5 rounded-[var(--radius-lg)]">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-[15px] font-bold text-[var(--text-1)]">Agent Activity</h3>
          <p className="text-[12px] text-[var(--text-3)] mt-0.5">Executions and cost over time</p>
        </div>
        <div className="flex gap-1 p-1 rounded-lg bg-[var(--surface-2)]">
          {(['7D', '30D', '90D'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded-md text-[12px] font-semibold transition-[background-color,color,box-shadow] ${
                period === p
                  ? 'bg-white dark:bg-white/10 text-violet-700 dark:text-violet-300 shadow-sm'
                  : 'text-[var(--text-3)] hover:text-[var(--text-1)]'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {!hasData ? (
        <div className="h-[220px] flex items-center justify-center text-[13px] text-[var(--text-3)]">
          No executions in this period yet
        </div>
      ) : (
        <AgentActivityArea data={data} isDark={isDark} height={220} />
      )}

      <div className="mt-4 flex gap-5 text-[12px]">
        <div className="flex items-center gap-2">
          <div className="w-3 h-[2px] rounded-full bg-violet-500" />
          <span className="text-[var(--text-2)]">Executions</span>
        </div>
      </div>
    </div>
  )
}
