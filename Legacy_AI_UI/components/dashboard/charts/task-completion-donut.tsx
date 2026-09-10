'use client'

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

export interface TaskCompletionDatum {
  name: string
  value: number
}

const ORDER = ['Completed', 'Slow', 'Incomplete']

export default function TaskCompletionDonut({
  data,
  colors,
  height = 160,
}: {
  data: TaskCompletionDatum[]
  colors: string[]
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={48}
          outerRadius={68}
          dataKey="value"
          startAngle={90}
          endAngle={-270}
          strokeWidth={0}
        >
          {data.map((entry, i) => (
            <Cell key={entry.name} fill={colors[ORDER.indexOf(entry.name)] ?? colors[i]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            fontSize: '12px',
          }}
          formatter={(value) => [`${value ?? 0}`, '']}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
