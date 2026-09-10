'use client'

import { useCallback, useState } from 'react'
import { Handle, Position, useReactFlow } from '@xyflow/react'
import { Star, X } from 'lucide-react'

export interface AgentNodeData extends Record<string, unknown> {
  name: string
  description?: string
  isMain: boolean
  /** Supervisor mode: the Supervisor is the entry point and routing is dynamic,
   *  so there is no entry point to pick and no inbound edge to receive. */
  supervised?: boolean
}

export function AgentNode({
  id,
  data,
  selected,
}: {
  id: string
  data: AgentNodeData
  selected?: boolean
}) {
  const { setNodes, deleteElements } = useReactFlow()
  const [deleting, setDeleting] = useState(false)

  const handleDelete = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      // Play the exit transition before actually removing the node — an
      // instant `deleteElements` teleports it away (AUDIT.md category 8).
      setDeleting(true)
      setTimeout(() => deleteElements({ nodes: [{ id }] }), 150)
    },
    [id, deleteElements],
  )

  const handleSetMain = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      setNodes(nds =>
        nds.map(n => ({ ...n, data: { ...n.data, isMain: n.id === id } })),
      )
    },
    [id, setNodes],
  )

  return (
    <div
      className={[
        'group relative w-[200px] rounded-2xl border-2 bg-[var(--surface)] transition-[border-color,box-shadow,opacity,transform] duration-150',
        deleting ? 'opacity-0 scale-90' : 'opacity-100 scale-100',
        data.isMain
          ? 'border-violet-500 shadow-lg shadow-violet-200 dark:shadow-violet-900/40'
          : 'border-[var(--border)] shadow-md hover:border-violet-300 dark:hover:border-violet-600',
        selected ? 'ring-2 ring-violet-400 ring-offset-1' : '',
      ].join(' ')}
    >
      {/* Delete */}
      <button
        onMouseDown={handleDelete}
        className="nodrag nopan absolute -top-2.5 -right-2.5 w-5 h-5 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 active:scale-90 transition-[opacity,transform] z-10 shadow-sm"
      >
        <X className="w-3 h-3" />
      </button>

      <Handle
        type="target"
        position={Position.Left}
        style={{ background: '#7c3aed', border: '2px solid white', width: 12, height: 12 }}
      />

      <div className="p-4">
        <div className="flex items-center gap-2.5 mb-3">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold shrink-0 text-white ${data.isMain ? 'bg-violet-600' : 'bg-[var(--surface-3)] text-[var(--text-2)]'}`}
          >
            {data.name[0]?.toUpperCase()}
          </div>
          <p className="text-[13px] font-bold text-[var(--text-1)] leading-tight truncate flex-1">
            {data.name}
          </p>
        </div>

        {data.description && (
          <p className="text-[11px] text-[var(--text-3)] mb-3 line-clamp-2 leading-relaxed">
            {data.description}
          </p>
        )}

        {data.supervised ? (
          <div className="flex items-center justify-center gap-1.5 py-1.5 rounded-xl text-[10px] font-bold text-[var(--text-3)] uppercase tracking-wider">
            Routed by Supervisor
          </div>
        ) : data.isMain ? (
          <div className="flex items-center justify-center gap-1.5 py-1.5 bg-violet-50 dark:bg-violet-500/20 rounded-xl">
            <Star className="w-3 h-3 fill-violet-600 text-violet-600" />
            <span className="text-[10px] font-bold text-violet-700 dark:text-violet-300 uppercase tracking-wider">
              Entry Point
            </span>
          </div>
        ) : (
          <button
            onMouseDown={handleSetMain}
            className="nodrag nopan w-full flex items-center justify-center gap-1.5 py-1.5 rounded-xl text-[11px] font-medium text-[var(--text-3)] hover:text-violet-600 hover:bg-violet-50 dark:hover:bg-violet-500/10 active:scale-[0.97] transition-[background-color,color,transform]"
          >
            <Star className="w-3 h-3" />
            Set as Entry Point
          </button>
        )}
      </div>

      {!data.supervised && (
        <Handle
          type="source"
          position={Position.Right}
          style={{ background: '#7c3aed', border: '2px solid white', width: 12, height: 12 }}
        />
      )}
    </div>
  )
}
