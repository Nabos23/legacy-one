'use client'

import { useMemo } from 'react'
import dynamic from 'next/dynamic'
import { useTheme } from '@/contexts/theme-context'

const TaskCompletionDonut = dynamic(() => import('./charts/task-completion-donut'), {
  ssr: false,
  loading: () => <div className="h-[160px]" />,
})
import { useRecentTraces } from '@/hooks/use-tracing'
import type { TracePublic } from '@/types'

const COLORS_LIGHT = ['#16a34a', '#d97706', '#dc2626']
const COLORS_DARK = ['#22c55e', '#f59e0b', '#ef4444']

// An execution is "Completed" when it produced output. Anything with no output
// is treated as Incomplete; high-latency (>5s) completions are flagged "Slow".
function classify(traces: TracePublic[]) {
  let completed = 0
  let slow = 0
  let incomplete = 0
  for (const t of traces) {
    const hasOutput = t.output != null && String(t.output).length > 0
    if (!hasOutput) incomplete += 1
    else if ((t.latency ?? 0) > 5000) slow += 1
    else completed += 1
  }
  return { completed, slow, incomplete }
}

export function TaskCompletionChart() {
  const { theme } = useTheme()
  const COLORS = theme === 'dark' ? COLORS_DARK : COLORS_LIGHT
  const { traces } = useRecentTraces()

  const { data, completionPct, total } = useMemo(() => {
    const { completed, slow, incomplete } = classify(traces)
    const total = completed + slow + incomplete
    const data = [
      { name: 'Completed', value: completed },
      { name: 'Slow', value: slow },
      { name: 'Incomplete', value: incomplete },
    ].filter(d => d.value > 0)
    const completionPct = total > 0 ? Math.round((completed / total) * 100) : 0
    return { data, completionPct, total }
  }, [traces])

  return (
    <div className="card-1 p-5 rounded-[var(--radius-lg)] flex flex-col">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-[15px] font-bold text-[var(--text-1)]">Execution Outcomes</h3>
        <span className="text-[26px] font-black text-[var(--text-1)] leading-none">{completionPct}%</span>
      </div>
      <p className="text-[12px] text-[var(--text-3)] mb-3">Of executions completed cleanly</p>

      <div className="relative flex-1 min-h-[160px]">
        {total === 0 ? (
          <div className="h-[160px] flex items-center justify-center text-[13px] text-[var(--text-3)]">
            No executions yet
          </div>
        ) : (
          <>
            <TaskCompletionDonut data={data} colors={COLORS} height={160} />

            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <p className="text-[18px] font-bold text-[var(--text-1)]">{total}</p>
              <p className="text-[11px] text-[var(--text-3)] font-medium">executions</p>
            </div>
          </>
        )}
      </div>

      {total > 0 && (
        <div className="mt-3 space-y-2">
          {data.map((item) => {
            const idx = ['Completed', 'Slow', 'Incomplete'].indexOf(item.name)
            const pct = total > 0 ? Math.round((item.value / total) * 100) : 0
            return (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[idx] }} />
                  <span className="text-[12.5px] text-[var(--text-2)]">{item.name}</span>
                </div>
                <span className="text-[12.5px] font-semibold text-[var(--text-1)]">{pct}%</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
