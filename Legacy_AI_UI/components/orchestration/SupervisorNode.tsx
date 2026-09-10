'use client'

import { Handle, Position } from '@xyflow/react'
import { Compass } from 'lucide-react'

export interface SupervisorNodeData extends Record<string, unknown> {
  /** How many agents the Supervisor can route to. */
  agentCount: number
}

/**
 * The Supervisor on the canvas.
 *
 * Unlike an agent node this is not deletable and has no "Set as Entry Point"
 * action: in supervisor mode the Supervisor *is* the entry point, it is
 * hardcoded rather than an agent document, and it always reaches every attached
 * agent. It has a source handle only — nothing routes *into* the Supervisor from
 * the canvas, since control returns to it automatically after each agent.
 */
export function SupervisorNode({ data }: { data: SupervisorNodeData }) {
  return (
    <div className="relative w-[200px] rounded-2xl border-2 border-violet-500 bg-[var(--surface)] shadow-lg shadow-violet-200 dark:shadow-violet-900/40">
      <div className="p-4">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-9 h-9 rounded-xl bg-violet-600 text-white flex items-center justify-center shrink-0">
            <Compass className="w-4 h-4" />
          </div>
          <p className="text-[13px] font-bold text-[var(--text-1)] leading-tight truncate flex-1">
            Supervisor
          </p>
        </div>

        <p className="text-[11px] text-[var(--text-3)] mb-3 leading-relaxed">
          Routes each request to the agent whose purpose, tools and connectors
          fit it best.
        </p>

        <div className="flex items-center justify-center gap-1.5 py-1.5 bg-violet-50 dark:bg-violet-500/20 rounded-xl">
          <span className="text-[10px] font-bold text-violet-700 dark:text-violet-300 uppercase tracking-wider">
            Entry Point · {data.agentCount}{' '}
            {data.agentCount === 1 ? 'agent' : 'agents'}
          </span>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        isConnectable={false}
        style={{ background: '#7c3aed', border: '2px solid white', width: 12, height: 12 }}
      />
    </div>
  )
}
