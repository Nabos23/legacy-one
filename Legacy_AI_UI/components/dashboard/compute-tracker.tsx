'use client'

import { Zap } from 'lucide-react'
import { useTraceStats } from '@/hooks/use-tracing'

function fmt(n?: number) {
  if (n == null) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

export function ComputeTracker() {
  const { stats, loading } = useTraceStats()

  const input = stats?.total_input_tokens ?? 0
  const output = stats?.total_output_tokens ?? 0
  const totalTokens = input + output
  const inputPct = totalTokens > 0 ? Math.round((input / totalTokens) * 100) : 0
  const outputPct = totalTokens > 0 ? Math.round((output / totalTokens) * 100) : 0
  const cost = stats?.total_cost ?? 0

  const meters = [
    { label: 'INPUT', pct: inputPct, raw: fmt(input), color: 'bg-violet-500', textColor: 'text-violet-600 dark:text-violet-400' },
    { label: 'OUTPUT', pct: outputPct, raw: fmt(output), color: 'bg-cyan-500', textColor: 'text-cyan-600 dark:text-cyan-400' },
  ]

  return (
    <div className="card-1 rounded-[var(--radius-lg)] overflow-hidden">
      {/* Gradient header */}
      <div className="relative p-5 pb-6
        bg-gradient-to-br from-violet-600 via-violet-700 to-indigo-800
        dark:from-violet-700 dark:via-violet-800 dark:to-indigo-900">
        <div className="absolute inset-0 bg-noise opacity-30" />
        <div className="absolute -top-6 -right-6 w-32 h-32 rounded-full bg-white/10 blur-2xl" />

        <div className="relative z-10">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-violet-200" />
              <h3 className="text-[14px] font-bold text-white">Usage Overview</h3>
            </div>
          </div>

          {/* Hero metric — total cost */}
          <div className="text-center">
            <p className="font-mono text-[40px] font-black text-white leading-none tracking-tight">
              {loading ? '—' : `$${cost.toFixed(4)}`}
            </p>
            <p className="text-[11px] text-violet-200/70 mt-2 font-medium uppercase tracking-wider">
              Total estimated cost
            </p>
          </div>

          <div className="flex items-center justify-center gap-6 mt-5">
            <div className="text-center">
              <p className="text-[18px] font-bold text-white">{fmt(stats?.total_traces)}</p>
              <p className="text-[10px] text-violet-200/70 uppercase tracking-wider">Executions</p>
            </div>
            <div className="w-px h-8 bg-white/20" />
            <div className="text-center">
              <p className="text-[18px] font-bold text-white">{fmt(totalTokens)}</p>
              <p className="text-[10px] text-violet-200/70 uppercase tracking-wider">Tokens</p>
            </div>
          </div>
        </div>
      </div>

      {/* Token split meters */}
      <div className="p-4 space-y-3">
        {meters.map(m => (
          <div key={m.label}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[12px] font-semibold text-[var(--text-2)]">{m.label}</span>
              <span className={`text-[12px] font-bold ${m.textColor}`}>{m.raw} · {m.pct}%</span>
            </div>
            <div className="h-1.5 bg-[var(--surface-3)] rounded-full overflow-hidden">
              <div
                className={`h-full w-full ${m.color} rounded-full origin-left transition-transform duration-700`}
                style={{ transform: `scaleX(${m.pct / 100})` }}
              />
            </div>
          </div>
        ))}
        {totalTokens === 0 && !loading && (
          <p className="text-[12px] text-[var(--text-3)] text-center pt-1">No token usage recorded yet</p>
        )}
      </div>
    </div>
  )
}
