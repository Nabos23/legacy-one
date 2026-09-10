'use client'

import { useState } from 'react'
import { Table2, Database, Hash, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { DbSchema } from '@/types'

interface DbSchemaTreeProps {
  schema: DbSchema
}

/**
 * SQL table node — `columns` is an array of { name, type, nullable }
 */
function TableNode({
  tableName,
  columns,
}: {
  tableName: string
  columns: Array<{ name: string; type: string; nullable: boolean }>
}) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-white/[0.04] w-full text-left transition-colors"
      >
        <ChevronRight className={cn('w-3.5 h-3.5 text-[var(--text-3)] transition-transform duration-200', open && 'rotate-90')} />
        <Table2 className="w-4 h-4 text-cyan-600 dark:text-cyan-400 shrink-0" />
        <span className="text-[13px] font-mono font-medium">{tableName}</span>
        <Badge variant="neutral" className="ml-auto text-[10px]">{columns.length} cols</Badge>
      </button>
      <div className={cn('grid transition-[grid-template-rows] duration-200 ease-out', open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
        <div className="overflow-hidden">
          <div className="ml-6 border-l border-[var(--border)] pl-3 mt-1 space-y-0.5">
            {columns.map(col => (
              <div key={col.name} className="flex items-center gap-2 py-1 text-[12px]">
                <Hash className="w-3 h-3 text-[var(--text-3)] shrink-0" />
                <span className="font-mono text-[var(--text-1)]">{col.name}</span>
                <Badge variant="neutral" className="text-[10px] px-1.5">{col.type}</Badge>
                {col.nullable && (
                  <Badge variant="warning" className="text-[10px] px-1.5">NULL</Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export function DbSchemaTree({ schema }: DbSchemaTreeProps) {
  // SQL schema: { kind: 'sql', tables: { tableName: [{name, type, nullable}] } }
  if (schema.kind === 'sql' && schema.tables) {
    return (
      <div className="space-y-1">
        {Object.entries(schema.tables).map(([tableName, columns]) => (
          <TableNode key={tableName} tableName={tableName} columns={columns} />
        ))}
      </div>
    )
  }

  // MongoDB schema: { kind: 'mongo', databases: { dbName: { collectionName: { fieldName: type } } } }
  if (schema.kind === 'mongo' && schema.databases) {
    return (
      <div className="space-y-2">
        {Object.entries(schema.databases).map(([dbName, collections]) => (
          <div key={dbName}>
            <div className="flex items-center gap-2 py-1.5 px-2">
              <Database className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <span className="text-[13px] font-mono font-medium">{dbName}</span>
            </div>
            <div className="ml-6 border-l border-[var(--border)] pl-3 space-y-0.5">
              {Object.entries(collections).map(([colName, fields]) => (
                <div key={colName}>
                  <div className="flex items-center gap-2 py-1 text-[12px]">
                    <Hash className="w-3 h-3 text-[var(--text-3)]" />
                    <span className="font-mono text-[var(--text-1)] font-medium">{colName}</span>
                    <Badge variant="neutral" className="text-[10px] px-1.5">{Object.keys(fields).length} fields</Badge>
                  </div>
                  <div className="ml-5 space-y-0.5">
                    {Object.entries(fields).map(([field, type]) => (
                      <div key={field} className="flex items-center gap-2 py-0.5 text-[11px]">
                        <span className="font-mono text-[var(--text-2)]">{field}</span>
                        <Badge variant="neutral" className="text-[10px] px-1">{type}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <p className="text-[13px] text-[var(--text-3)] italic">No schema available</p>
  )
}

interface DbSchemaSheetContentProps {
  connectionId: string
  createdAt: string
}

export function DbSchemaSheetContent({ connectionId, createdAt }: DbSchemaSheetContentProps) {
  const [schema, setSchema] = useState<DbSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useState(() => {
    import('@/lib/api').then(({ dbConnectionsApi }) =>
      dbConnectionsApi.getSchema(connectionId)
        .then(setSchema)
        .catch(() => setError(true))
        .finally(() => setLoading(false))
    )
  })

  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-8 bg-white/[0.04] rounded" />
        ))}
      </div>
    )
  }

  if (error || !schema) {
    return (
      <div className="text-center py-8 text-[var(--text-3)]">
        <Database className={cn('w-8 h-8 mx-auto mb-2')} />
        <p className="text-[13px]">Schema not available</p>
      </div>
    )
  }

  return (
    <div>
      <DbSchemaTree schema={schema} />
      <p className="text-[11px] text-[var(--text-3)] mt-4">
        Last fetched: {new Date(createdAt).toLocaleString()}
      </p>
    </div>
  )
}
