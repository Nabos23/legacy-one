'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  Database,
  Table2,
  Hash,
  ChevronRight,
  Edit2,
  Loader2,
  Play,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { PageHeader } from '@/components/ui/page-header'
import { InfoBox } from '@/components/ui/info-box'
import { dbConnectionsApi } from '@/lib/api'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import { cn } from '@/lib/utils'
import { useToast } from '@/hooks/use-toast'

interface SqlColumn { name: string; type: string; nullable: boolean }
interface SqlTableInfo { columns?: SqlColumn[]; description?: string | null }
interface MongoCollInfo { description?: string | null; [key: string]: unknown }
interface FirebaseFieldInfo { types?: string[] }
interface FirebaseCollInfo {
  fields?: Record<string, FirebaseFieldInfo | unknown>
  description?: string | null
  sample_document_count?: number
}

interface RichSchema {
  kind: 'sql' | 'mongo' | 'firebase'
  dialect?: string
  database?: string
  project_id?: string
  database_id?: string
  tables?: Record<string, SqlTableInfo>
  databases?: Record<string, Record<string, MongoCollInfo>>
  collections?: Record<string, FirebaseCollInfo>
}

function SqlTableNode({ name, info }: { name: string; info: SqlTableInfo }) {
  const [open, setOpen] = useState(false)
  const cols = info.columns ?? []
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-white/[0.04] w-full text-left transition-colors"
      >
        <ChevronRight className={cn('w-3.5 h-3.5 text-[var(--text-3)] transition-transform duration-200', open && 'rotate-90')} />
        <Table2 className="w-4 h-4 text-cyan-600 dark:text-cyan-400 shrink-0" />
        <span className="text-[13px] font-mono font-medium">{name}</span>
        <Badge variant="neutral" className="ml-auto text-[10px]">{cols.length} cols</Badge>
      </button>

      {info.description && (
        <p className="ml-10 mr-2 text-[12px] text-[var(--text-2)] italic mb-1">{info.description}</p>
      )}

      {cols.length > 0 && (
        <div className={cn('grid transition-[grid-template-rows] duration-200 ease-out', open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
          <div className="overflow-hidden">
            <div className="ml-6 border-l border-[var(--border)] pl-3 mt-1 space-y-0.5">
              {cols.map(col => (
                <div key={col.name} className="flex items-center gap-2 py-1 text-[12px]">
                  <Hash className="w-3 h-3 text-[var(--text-3)] shrink-0" />
                  <span className="font-mono text-[var(--text-1)]">{col.name}</span>
                  <Badge variant="neutral" className="text-[10px] px-1.5">{col.type}</Badge>
                  {col.nullable && <Badge variant="warning" className="text-[10px] px-1.5">NULL</Badge>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MongoCollNode({ name, info }: { name: string; info: MongoCollInfo }) {
  return (
    <div className="py-1 px-2">
      <div className="flex items-center gap-2">
        <Hash className="w-3 h-3 text-[var(--text-3)] shrink-0" />
        <span className="font-mono text-[13px] font-medium text-[var(--text-1)]">{name}</span>
      </div>
      {info.description && (
        <p className="ml-5 text-[12px] text-[var(--text-2)] italic mt-0.5">{info.description}</p>
      )}
    </div>
  )
}

function FirebaseCollNode({ name, info }: { name: string; info: FirebaseCollInfo }) {
  const [open, setOpen] = useState(false)
  const fields = Object.entries(info.fields ?? {})
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-white/[0.04] w-full text-left transition-colors"
      >
        <ChevronRight className={cn('w-3.5 h-3.5 text-[var(--text-3)] transition-transform duration-200', open && 'rotate-90')} />
        <Database className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
        <span className="text-[13px] font-mono font-medium">{name}</span>
        <Badge variant="neutral" className="ml-auto text-[10px]">{fields.length} fields</Badge>
      </button>

      {info.description && (
        <p className="ml-10 mr-2 text-[12px] text-[var(--text-2)] italic mb-1">{info.description}</p>
      )}

      {fields.length > 0 && (
        <div className={cn('grid transition-[grid-template-rows] duration-200 ease-out', open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
          <div className="overflow-hidden">
            <div className="ml-6 border-l border-[var(--border)] pl-3 mt-1 space-y-0.5">
              {fields.map(([field, raw]) => {
                const typed = raw as FirebaseFieldInfo
                const label = Array.isArray(typed.types) ? typed.types.join(' | ') : 'unknown'
                return (
                  <div key={field} className="flex items-center gap-2 py-1 text-[12px]">
                    <Hash className="w-3 h-3 text-[var(--text-3)] shrink-0" />
                    <span className="font-mono text-[var(--text-1)]">{field}</span>
                    <Badge variant="neutral" className="text-[10px] px-1.5">{label}</Badge>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function DbConnectionSchemaPage() {
  const { id } = useParams<{ id: string }>()
  const { toast } = useToast()
  const [schema, setSchema] = useState<RichSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [query, setQuery] = useState('{"collection":"users","limit":10}')
  const [queryResult, setQueryResult] = useState('')
  const [querying, setQuerying] = useState(false)
  const [connectionName, setConnectionName] = useState('')
  useBreadcrumbLabel(id, connectionName)

  useEffect(() => {
    dbConnectionsApi.get(id).then(c => setConnectionName(c.name ?? '')).catch(() => {})
  }, [id])

  useEffect(() => {
    dbConnectionsApi.getSchema(id)
      .then(s => {
        const rich = s as unknown as RichSchema
        setSchema(rich)
        if (rich.kind === 'sql') {
          setQuery('select * from your_table limit 10')
        } else if (rich.kind === 'mongo') {
          setQuery('{"collection":"users","filter":{},"limit":10}')
        } else {
          const firstCollection = Object.keys(rich.collections ?? {})[0] || 'users'
          setQuery(JSON.stringify({ collection: firstCollection, limit: 10 }, null, 2))
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  const runQuery = async () => {
    if (!query.trim()) {
      toast.error('Query is required')
      return
    }
    setQuerying(true)
    try {
      const result = await dbConnectionsApi.query(id, { query })
      setQueryResult(result.result)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Query failed')
    } finally {
      setQuerying(false)
    }
  }

  const actions = (
    <Link href={`/client/db-connections/${id}/edit`}>
      <Button variant="secondary" size="sm">
        <Edit2 className="w-4 h-4 mr-2" />
        Edit Descriptions
      </Button>
    </Link>
  )

  return (
    <>
      <PageHeader
        title="Schema"
        description="Database structure and AI-generated descriptions"
        actions={actions}
      />

      <div className="max-w-2xl mx-auto space-y-5">
        {loading && (
          <div className="space-y-2 animate-pulse">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-10 rounded-[var(--radius-md)] bg-[var(--surface-2)]" />
            ))}
          </div>
        )}

        {!loading && (error || !schema) && (
          <div className="flex flex-col items-center justify-center py-16 text-center text-[var(--text-3)]">
            <Database className="w-10 h-10 mb-3" />
            <p className="text-[14px] font-medium">Schema not available</p>
            <p className="text-[13px] mt-1">The schema may still be syncing. Try again shortly.</p>
          </div>
        )}

        {!loading && schema && (
          <>
            <div className="glass p-4 rounded-[var(--radius-lg)]">
              <div className="flex flex-wrap items-center gap-2 mb-4 pb-3 border-b border-[var(--border)]">
                <Badge variant="neutral">
                  {schema.kind.toUpperCase()}{schema.dialect ? ` / ${schema.dialect}` : ''}
                </Badge>
                {schema.kind === 'firebase' && schema.project_id && (
                  <Badge variant="info">{schema.project_id}</Badge>
                )}
                {schema.kind === 'sql' && schema.tables && (
                  <Badge variant="info">{Object.keys(schema.tables).length} tables</Badge>
                )}
                {schema.kind === 'mongo' && schema.databases && (
                  <Badge variant="info">
                    {Object.values(schema.databases).reduce((s, c) => s + Object.keys(c).length, 0)} collections
                  </Badge>
                )}
                {schema.kind === 'firebase' && schema.collections && (
                  <Badge variant="info">{Object.keys(schema.collections).length} collections</Badge>
                )}
              </div>

              {schema.kind === 'sql' && schema.tables && (
                <div className="space-y-0.5">
                  {Object.entries(schema.tables).map(([name, info]) => (
                    <SqlTableNode key={name} name={name} info={info} />
                  ))}
                </div>
              )}

              {schema.kind === 'mongo' && schema.databases && (
                <div className="space-y-3">
                  {Object.entries(schema.databases).map(([dbName, colls]) => (
                    <div key={dbName}>
                      <div className="flex items-center gap-2 py-1.5 px-2">
                        <Database className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                        <span className="text-[13px] font-mono font-semibold">{dbName}</span>
                      </div>
                      <div className={cn('ml-6 border-l border-[var(--border)] pl-3 space-y-0.5')}>
                        {Object.entries(colls).map(([collName, info]) => (
                          <MongoCollNode key={collName} name={collName} info={info} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {schema.kind === 'firebase' && schema.collections && (
                <div className="space-y-0.5">
                  {Object.entries(schema.collections).map(([name, info]) => (
                    <FirebaseCollNode key={name} name={name} info={info} />
                  ))}
                </div>
              )}
            </div>

            <div className="glass p-4 rounded-[var(--radius-lg)] space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-[15px] font-semibold">Test Read Query</h2>
                  <p className="text-[12px] text-[var(--text-3)]">
                    Run a read-only query against this saved connection.
                  </p>
                </div>
                <Button variant="primary" size="sm" onClick={runQuery} disabled={querying}>
                  {querying ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                  Run
                </Button>
              </div>
              {schema.kind === 'firebase' && (
                <InfoBox variant="info">
                  Firestore queries use JSON with collection, optional filters, optional order_by, and limit.
                </InfoBox>
              )}
              <Textarea
                value={query}
                onChange={e => setQuery(e.target.value)}
                className="min-h-[110px] font-mono text-[12px]"
              />
              {queryResult && (
                <pre className="max-h-[320px] overflow-auto whitespace-pre-wrap rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-2)] p-3 text-[12px] text-[var(--text-1)]">
                  {queryResult}
                </pre>
              )}
            </div>
          </>
        )}

        <div>
          <Link href="/client/db-connections">
            <Button variant="secondary">Back to Connections</Button>
          </Link>
        </div>
      </div>
    </>
  )
}
