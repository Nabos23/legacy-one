'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Loader2, Lock, Eye, EyeOff, Database, Save, FileJson, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { FormField } from '@/components/ui/form-field'
import { PageHeader } from '@/components/ui/page-header'
import { InfoBox } from '@/components/ui/info-box'
import { useToast } from '@/hooks/use-toast'
import { dbConnectionsApi } from '@/lib/api'
import { useBreadcrumbLabel } from '@/contexts/breadcrumb-context'
import type { DbConnectionTargetInput, DbSchema } from '@/types'

const DEFAULT_FIREBASE_DATABASE = '(default)'
type DatabaseConnectionType = 'postgresql' | 'mysql' | 'sqlite' | 'mssql' | 'mongodb' | 'firebase' | 'other'
type TableMap = Record<string, { columns?: unknown[]; description?: string }>
type CollMap = Record<string, Record<string, { description?: string }>>

const DATABASE_TYPE_OPTIONS: Array<{ value: DatabaseConnectionType; label: string }> = [
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL / MariaDB' },
  { value: 'sqlite', label: 'SQLite' },
  { value: 'mssql', label: 'Microsoft SQL Server' },
  { value: 'mongodb', label: 'MongoDB' },
  { value: 'firebase', label: 'Firebase / Firestore' },
  { value: 'other', label: 'Other' },
]

const CONNECTION_FORMATS: Record<Exclude<DatabaseConnectionType, 'firebase'>, string> = {
  postgresql: 'postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE',
  mysql: 'mysql://USERNAME:PASSWORD@HOST:PORT/DATABASE',
  sqlite: 'sqlite:///PATH/TO/DATABASE.db',
  mssql: 'mssql+pyodbc://USERNAME:PASSWORD@HOST:PORT/DATABASE?driver=DRIVER',
  mongodb: 'mongodb://USERNAME:PASSWORD@HOST:PORT/DATABASE',
  other: 'DIALECT://USERNAME:PASSWORD@HOST:PORT/DATABASE',
}

function getDatabaseTypeLabel(type: DatabaseConnectionType) {
  return DATABASE_TYPE_OPTIONS.find(option => option.value === type)?.label ?? type
}

function extractDescriptions(schema: DbSchema): Record<string, string> {
  const out: Record<string, string> = {}
  if (schema.kind === 'sql' && schema.tables) {
    const tables = schema.tables as unknown as TableMap
    for (const [name, info] of Object.entries(tables)) {
      out[name] = info?.description ?? ''
    }
  } else if (schema.kind === 'mongo' && schema.databases) {
    const dbs = schema.databases as unknown as CollMap
    for (const [db, colls] of Object.entries(dbs)) {
      for (const [coll, info] of Object.entries(colls)) {
        out[`${db}.${coll}`] = info?.description ?? ''
      }
    }
  } else if (schema.kind === 'firebase' && schema.collections) {
    for (const [name, info] of Object.entries(schema.collections)) {
      out[name] = info?.description ?? ''
    }
  }
  return out
}

function parseFirebaseServiceAccount(raw: string): Record<string, unknown> {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error('Firebase service account must be valid JSON')
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Firebase service account must be a JSON object')
  }
  const account = parsed as Record<string, unknown>
  const missing = ['project_id', 'client_email', 'private_key'].filter(key => !account[key])
  if (missing.length > 0) {
    throw new Error(`Firebase service account JSON is missing: ${missing.join(', ')}`)
  }
  return account
}

export default function EditDbConnectionPage() {
  const { id } = useParams<{ id: string }>()
  const { toast } = useToast()

  const [showPassword, setShowPassword] = useState(false)
  const [connectionName, setConnectionName] = useState('')
  useBreadcrumbLabel(id, connectionName)
  const [databaseType, setDatabaseType] = useState<DatabaseConnectionType>('postgresql')
  const [detailsLoading, setDetailsLoading] = useState(true)
  const [updatingDetails, setUpdatingDetails] = useState(false)
  const [newConnectionString, setNewConnectionString] = useState('')
  const [firebaseServiceAccount, setFirebaseServiceAccount] = useState('')
  const [firebaseDatabaseId, setFirebaseDatabaseId] = useState(DEFAULT_FIREBASE_DATABASE)
  const [updatingConn, setUpdatingConn] = useState(false)

  const [descriptions, setDescriptions] = useState<Record<string, string>>({})
  const [schemaLoading, setSchemaLoading] = useState(true)
  const [updatingDesc, setUpdatingDesc] = useState(false)

  const [fieldErrors, setFieldErrors] = useState<{ name?: string; connectionTarget?: string }>({})

  const loadSchema = useCallback(async () => {
    setSchemaLoading(true)
    try {
      const s = await dbConnectionsApi.getSchema(id)
      setDescriptions(extractDescriptions(s))
      if (s.kind === 'firebase') {
        setDatabaseType('firebase')
        setFirebaseDatabaseId(s.database_id || DEFAULT_FIREBASE_DATABASE)
      } else if (s.kind === 'mongo') {
        setDatabaseType('mongodb')
      } else if (s.dialect && DATABASE_TYPE_OPTIONS.some(option => option.value === s.dialect)) {
        setDatabaseType(s.dialect as DatabaseConnectionType)
      }
    } catch {
      // schema may not exist yet for this connection
    } finally {
      setSchemaLoading(false)
    }
  }, [id])

  useEffect(() => {
    let cancelled = false

    const loadDetails = async () => {
      setDetailsLoading(true)
      try {
        const conn = await dbConnectionsApi.get(id)
        if (cancelled) return
        setConnectionName(conn.name ?? '')
        if (conn.connection_type === 'firebase') {
          setDatabaseType('firebase')
        } else if (conn.connection_type && DATABASE_TYPE_OPTIONS.some(option => option.value === conn.connection_type)) {
          setDatabaseType(conn.connection_type as DatabaseConnectionType)
        }
      } catch (err) {
        if (!cancelled) {
          toast.error(err instanceof Error ? err.message : 'Failed to load connection details')
        }
      } finally {
        if (!cancelled) {
          setDetailsLoading(false)
        }
      }
    }

    loadDetails()

    return () => {
      cancelled = true
    }
  }, [id])
  useEffect(() => { loadSchema() }, [loadSchema])

  const connectionType = databaseType

  const handleUpdateDetails = async () => {
    const name = connectionName.trim()
    if (!name) {
      setFieldErrors(prev => ({ ...prev, name: 'Connection name is required' }))
      return
    }
    setFieldErrors(prev => ({ ...prev, name: undefined }))
    setUpdatingDetails(true)
    try {
      await dbConnectionsApi.update(id, {
        name,
        connection_type: connectionType,
      })
      toast.success('Connection details updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update connection details')
    } finally {
      setUpdatingDetails(false)
    }
  }

  const buildConnectionTarget = (): DbConnectionTargetInput => {
    if (databaseType === 'firebase') {
      return {
        firebase: {
          service_account: parseFirebaseServiceAccount(firebaseServiceAccount),
          database_id: firebaseDatabaseId.trim() || DEFAULT_FIREBASE_DATABASE,
        },
      }
    }
    if (!newConnectionString.trim()) {
      throw new Error('Enter a new connection string')
    }
    return { connection_string: newConnectionString.trim() }
  }

  const handleUpdateConnection = async () => {
    let connectionTarget: DbConnectionTargetInput
    try {
      connectionTarget = buildConnectionTarget()
    } catch (err) {
      setFieldErrors(prev => ({
        ...prev,
        connectionTarget: err instanceof Error ? err.message : 'Invalid connection target',
      }))
      return
    }
    setFieldErrors(prev => ({ ...prev, connectionTarget: undefined }))
    setUpdatingConn(true)
    try {
      await dbConnectionsApi.update(id, {
        name: connectionName.trim() || undefined,
        connection_type: connectionType,
        ...connectionTarget,
      })
      toast.success('Connection updated - schema will re-sync in the background')
      setNewConnectionString('')
      setFirebaseServiceAccount('')
      await loadSchema()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update connection')
    } finally {
      setUpdatingConn(false)
    }
  }

  const handleUpdateDescriptions = async () => {
    setUpdatingDesc(true)
    try {
      await dbConnectionsApi.updateDescriptions(id, { table_descriptions: descriptions })
      toast.success('Descriptions updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update descriptions')
    } finally {
      setUpdatingDesc(false)
    }
  }

  const tableKeys = Object.keys(descriptions)
  const connectionReady = databaseType === 'firebase'
    ? firebaseServiceAccount.trim().length > 0
    : newConnectionString.trim().length > 0

  return (
    <>
      <PageHeader
        title="Edit DB Connection"
        description="Update the connection target or refine table descriptions"
      />

      <div className="max-w-2xl mx-auto space-y-6">
        <div className="glass p-6 rounded-[var(--radius-lg)] space-y-4">
          <h2 className="text-[15px] font-semibold">Connection Details</h2>

          <FormField label="Connection Name" required error={fieldErrors.name}>
            <Input
              value={connectionName}
              onChange={e => {
                setConnectionName(e.target.value)
                setFieldErrors(prev => ({ ...prev, name: undefined }))
              }}
              placeholder="Production analytics"
              leftIcon={<Database className="w-4 h-4" />}
              disabled={detailsLoading}
            />
          </FormField>

          <FormField label="Database Type" required>
            <Select
              value={databaseType}
              onValueChange={value => setDatabaseType(value as DatabaseConnectionType)}
              options={DATABASE_TYPE_OPTIONS}
              disabled={detailsLoading}
            />
          </FormField>

          <div className="flex justify-end">
            <Button
              variant="primary"
              onClick={handleUpdateDetails}
              disabled={updatingDetails || detailsLoading}
            >
              {updatingDetails
                ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                : <Save className="w-4 h-4 mr-2" />}
              Update Details
            </Button>
          </div>
        </div>

        <div className="glass p-6 rounded-[var(--radius-lg)] space-y-4">
          <h2 className="text-[15px] font-semibold">Update Connection Target</h2>

          {databaseType !== 'firebase' ? (
            <div>
              <FormField
                label="New Connection String"
                error={fieldErrors.connectionTarget}
                hint="Changing the string re-fetches the schema and re-indexes vectors automatically."
              >
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={newConnectionString}
                  onChange={e => {
                    setNewConnectionString(e.target.value)
                    setFieldErrors(prev => ({ ...prev, connectionTarget: undefined }))
                  }}
                  placeholder={CONNECTION_FORMATS[databaseType]}
                  leftIcon={<Lock className="w-4 h-4" />}
                  className="font-mono"
                  rightElement={
                    <button
                      type="button"
                      onClick={() => setShowPassword(v => !v)}
                      className="text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  }
                />
              </FormField>
              <p className="flex items-start gap-1.5 text-[11px] text-[var(--text-2)] mt-2">
                <Info className="w-3.5 h-3.5 shrink-0 mt-px" />
                <span>
                  {getDatabaseTypeLabel(databaseType)} format:{' '}
                  <code className="font-mono text-[var(--text-1)]">{CONNECTION_FORMATS[databaseType]}</code>
                </span>
              </p>
            </div>
          ) : (
            <>
              <FormField label="Service Account JSON" error={fieldErrors.connectionTarget}>
                <Textarea
                  value={firebaseServiceAccount}
                  onChange={e => {
                    setFirebaseServiceAccount(e.target.value)
                    setFieldErrors(prev => ({ ...prev, connectionTarget: undefined }))
                  }}
                  placeholder='{"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}'
                  className="min-h-[180px] font-mono text-[12px]"
                />
              </FormField>
              <FormField label="Firestore Database ID">
                <Input
                  value={firebaseDatabaseId}
                  onChange={e => setFirebaseDatabaseId(e.target.value)}
                  leftIcon={<FileJson className="w-4 h-4" />}
                  placeholder={DEFAULT_FIREBASE_DATABASE}
                />
              </FormField>
            </>
          )}

          <InfoBox variant="warning">
            Updating the connection target will re-encrypt it and re-fetch the database schema.
          </InfoBox>

          <div className="flex justify-end">
            <Button
              variant="primary"
              onClick={handleUpdateConnection}
              disabled={updatingConn || !connectionReady}
            >
              {updatingConn
                ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                : <Save className="w-4 h-4 mr-2" />}
              Update Connection
            </Button>
          </div>
        </div>

        <div className="glass p-6 rounded-[var(--radius-lg)] space-y-4">
          <h2 className="text-[15px] font-semibold">Table Descriptions</h2>
          <p className="text-[13px] text-[var(--text-2)]">
            Edit descriptions to help agents understand each table or collection.
          </p>

          {schemaLoading ? (
            <div className="space-y-2 animate-pulse">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-20 rounded-[var(--radius-md)] bg-[var(--surface-2)]" />
              ))}
            </div>
          ) : tableKeys.length === 0 ? (
            <InfoBox variant="info">
              No schema found for this connection. Update the connection target to fetch one.
            </InfoBox>
          ) : (
            <>
              <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
                {tableKeys.map(key => (
                  <div
                    key={key}
                    className="p-3 rounded-[var(--radius-md)] bg-[var(--surface-2)] border border-[var(--border)]"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Database className="w-3.5 h-3.5 text-violet-600 dark:text-violet-400 shrink-0" />
                      <span className="font-mono text-[12px] font-medium text-[var(--text-1)]">{key}</span>
                    </div>
                    <Textarea
                      value={descriptions[key]}
                      onChange={e => setDescriptions(prev => ({ ...prev, [key]: e.target.value }))}
                      placeholder="Describe this table or collection..."
                      className="min-h-[56px] text-[13px]"
                      rows={2}
                    />
                  </div>
                ))}
              </div>

              <div className="flex justify-end">
                <Button variant="primary" onClick={handleUpdateDescriptions} disabled={updatingDesc}>
                  {updatingDesc
                    ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    : <Save className="w-4 h-4 mr-2" />}
                  Update Descriptions
                </Button>
              </div>
            </>
          )}
        </div>

        <Link href="/client/db-connections">
          <Button variant="secondary">Back to Connections</Button>
        </Link>
      </div>
    </>
  )
}
