'use client'

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export interface AgentActivityDatum {
  name: string
  executions: number
  cost: number
}

export default function AgentActivityArea({
  data,
  isDark,
  height = 220,
}: {
  data: AgentActivityDatum[]
  isDark: boolean
  height?: number
}) {
  const tickColor = isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.4)'
  const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)'
  const tooltipBg = isDark ? 'rgba(14,14,30,0.97)' : 'rgba(255,255,255,0.98)'
  const tooltipBdr = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'
  const tooltipText = isDark ? '#f4f4f5' : '#09090b'

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <defs>
          <linearGradient id="gradExec" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#7c3aed" stopOpacity={isDark ? 0.3 : 0.2} />
            <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
        <XAxis dataKey="name" tick={{ fill: tickColor, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: tickColor, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={{
            backgroundColor: tooltipBg,
            border: `1px solid ${tooltipBdr}`,
            borderRadius: '10px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
            color: tooltipText,
            fontSize: '12px',
          }}
          cursor={{ stroke: gridColor, strokeWidth: 1 }}
        />
        <Area
          type="monotone"
          dataKey="executions"
          stroke="#7c3aed"
          strokeWidth={2}
          fill="url(#gradExec)"
          animationDuration={600}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
