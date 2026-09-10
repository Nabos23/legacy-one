'use client'

import { cn } from '@/lib/utils'

/**
 * Ambient "agent network" — a faint, low-opacity constellation of connected
 * nodes that echoes the multi-agent architecture. Decorative background only:
 * monochrome violet, very low opacity, no gradients. Two fixed layouts so
 * instances vary without random (SSR-safe). Reduced-motion safe (pulse off).
 */
type Layout = { nodes: [number, number][]; edges: [number, number][]; pulse: number[] }

const LAYOUTS: Record<'a' | 'b', Layout> = {
  a: {
    nodes: [
      [40, 70], [120, 32], [108, 130], [205, 78], [275, 150], [180, 190], [300, 56],
    ],
    edges: [[0, 1], [0, 2], [1, 3], [2, 3], [3, 4], [3, 6], [4, 5], [2, 5]],
    pulse: [3, 5],
  },
  b: {
    nodes: [
      [60, 44], [22, 140], [140, 92], [120, 200], [232, 40], [262, 146], [198, 168],
    ],
    edges: [[0, 2], [1, 2], [2, 3], [2, 4], [4, 5], [5, 6], [3, 6]],
    pulse: [2, 4],
  },
}

export function AgentField({
  variant = 'a',
  className,
  delay = 0,
}: {
  variant?: 'a' | 'b'
  className?: string
  delay?: number
}) {
  const l = LAYOUTS[variant]
  return (
    <div
      aria-hidden
      style={{ animationDelay: `${delay}s` }}
      className={cn(
        'pointer-events-none absolute animate-floatY select-none text-violet-500 opacity-[0.24] dark:opacity-[0.30]',
        className,
      )}
    >
      <svg width="320" height="220" viewBox="0 0 320 220" fill="none">
        {l.edges.map(([a, b], i) => (
          <line
            key={i}
            x1={l.nodes[a][0]}
            y1={l.nodes[a][1]}
            x2={l.nodes[b][0]}
            y2={l.nodes[b][1]}
            stroke="currentColor"
            strokeWidth="1"
            opacity="0.55"
          />
        ))}
        {l.nodes.map(([x, y], i) => (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={l.pulse.includes(i) ? 3.6 : 2.2}
            fill="currentColor"
            className={l.pulse.includes(i) ? 'animate-nodePulse' : undefined}
            style={l.pulse.includes(i) ? { animationDelay: `${i * 0.4}s` } : undefined}
          />
        ))}
      </svg>
    </div>
  )
}
