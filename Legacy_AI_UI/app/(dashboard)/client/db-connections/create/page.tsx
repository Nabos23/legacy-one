'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Loader2, Lock, Eye, EyeOff, Database, FileJson, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { FormField } from '@/components/ui/form-field'
import { PageHeader } from '@/components/ui/page-header'
import { Stepper } from '@/components/ui/stepper'
import { InfoBox } from '@/components/ui/info-box'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import { dbConnectionsApi } from '@/lib/api'
import { useAuth } from '@/contexts/auth-context'
import { useOrganizations } from '@/hooks/use-organizations'
import type { DbConnectionPreviewResponse, DbConnectionTargetInput } from '@/types'

const STEPS = ['Connect', 'Review & Save']
const DEFAULT_FIREBASE_DATABASE = '(default)'
type DatabaseConnectionType = 'postgresql' | 'mysql' | 'sqlite' | 'mssql' | 'mongodb' | 'firebase' | 'other'

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

function extractDescriptions(preview: DbConnectionPreviewResponse): Record<string, string> {
  const out: Record<string, string> = {}
  if (preview.kind === 'sql' && preview.tables) {
    for (const [name, info] of Object.entries(preview.tables)) {
      out[name] = info.description ?? ''
    }
  } else if (preview.kind === 'mongo' && preview.databases) {
    for (const [db, colls] of Object.entries(preview.databases)) {
      for (const [coll, info] of Object.entries(colls)) {
        out[`${db}.${coll}`] = info.description ?? ''
      }
    }
  } else if (preview.kind === 'firebase' && preview.collections) {
    for (const [name, info] of Object.entries(preview.collections)) {
      out[name] = info.description ?? ''
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

function getConnectionTypeLabel(type: string) {
  if (type === 'firebase') return 'Firebase'
  return DATABASE_TYPE_OPTIONS.find(option => option.value === type)?.label ?? type
}

export default function CreateDbConnectionPage() {
  const router = useRouter()
  const { toast } = useToast()
  const { user } = useAuth()
  const isSuperAdmin = user?.role === 'super_admin'
  const { data: orgsData } = useOrganizations(1, undefined, 1000)
  const orgs = orgsData?.items ?? []

  const [step, setStep] = useState(0)
  const [showPassword, setShowPassword] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [saving, setSaving] = useState(false)

  const [connectionName, setConnectionName] = useState('')
  const [databaseType, setDatabaseType] = useState<DatabaseConnectionType>('postgresql')
  const [connectionString, setConnectionString] = useState('')
  const [firebaseServiceAccount, setFirebaseServiceAccount] = useState('')
  const [firebaseDatabaseId, setFirebaseDatabaseId] = useState(DEFAULT_FIREBASE_DATABASE)
  const [orgId, setOrgId] = useState('')
  const [preview, setPreview] = useState<DbConnectionPreviewResponse | null>(null)
  const [descriptions, setDescriptions] = useState<Record<string, string>>({})
  const [fieldErrors, setFieldErrors] = useState<{
    org?: string
    name?: string
    connectionString?: string
    serviceAccount?: string
  }>({})

  useEffect(() => {
    if (isSuperAdmin && orgs.length > 0 && !orgId) {
      setOrgId(orgs[0].id!)
    }
  }, [isSuperAdmin, orgs, orgId])

  const effectiveOrgId = isSuperAdmin ? orgId : (user?.organization_id ?? '')
  const connectionType = databaseType

  const buildConnectionMetadata = () => {
    const name = connectionName.trim()
    if (!name) {
      throw new Error('Connection name is required')
    }
    return {
      name,
      connection_type: connectionType,
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
    if (!connectionString.trim()) {
      throw new Error('Connection string is required')
    }
    return { connection_string: connectionString.trim() }
  }

  const handlePreview = async () => {
    setFieldErrors({})
    if (!effectiveOrgId) {
      setFieldErrors(prev => ({ ...prev, org: 'Organization is required' }))
      return
    }
    let metadata: ReturnType<typeof buildConnectionMetadata>
    try {
      metadata = buildConnectionMetadata()
    } catch (err) {
      setFieldErrors(prev => ({ ...prev, name: err instanceof Error ? err.message : 'Invalid connection name' }))
      return
    }
    let connectionTarget: DbConnectionTargetInput
    try {
      connectionTarget = buildConnectionTarget()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Invalid connection target'
      if (databaseType === 'firebase') {
        setFieldErrors(prev => ({ ...prev, serviceAccount: message }))
      } else {
        setFieldErrors(prev => ({ ...prev, connectionString: message }))
      }
      return
    }
    setPreviewing(true)
    try {
      const result = await dbConnectionsApi.preview({
        organization_id: effectiveOrgId,
        connection_type: connectionType,
        name: metadata.name,
        ...connectionTarget,
      })
      setPreview(result)
      if (result.formatted_connection_string) {
        setConnectionString(result.formatted_connection_string)
      }
      setDescriptions(extractDescriptions(result))
      setStep(1)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect to database')
    } finally {
      setPreviewing(false)
    }
  }

  const handleSave = async () => {
    if (!preview) return
    setSaving(true)
    try {
      const metadata = buildConnectionMetadata()
      const connectionTarget = buildConnectionTarget()
      await dbConnectionsApi.create({
        organization_id: effectiveOrgId,
        ...metadata,
        ...connectionTarget,
        table_descriptions: descriptions,
      })
      toast.success('Connection saved successfully')
      router.push('/client/db-connections')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save connection')
    } finally {
      setSaving(false)
    }
  }

  const tableKeys = preview ? Object.keys(descriptions) : []
  const objectLabel = preview?.kind === 'mongo' || preview?.kind === 'firebase' ? 'collections' : 'tables'

  return (
    <>
      {previewing && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
          role="status"
          aria-live="polite"
          aria-label="Previewing database connection"
        >
          <div className="glass-card flex max-w-sm flex-col items-center rounded-2xl border border-[var(--border)] bg-[var(--surface)]/95 px-8 py-7 text-center shadow-2xl">
            <Loader2 className="h-9 w-9 animate-spin text-violet-500" aria-hidden="true" />
            <p className="mt-4 text-[15px] font-medium text-[var(--text-1)]">
              Previewing connection
            </p>
            <p className="mt-1 text-[12px] text-[var(--text-2)]">
              Connecting to your database and analysing its schema...
            </p>
          </div>
        </div>
      )}

      <PageHeader
        title="Add DB Connection"
        description="Store an encrypted database connection for your tools"
      />

      <div className="max-w-2xl mx-auto">
        <Stepper steps={STEPS} currentStep={step} />

        <div className="mt-8 glass p-6 rounded-[var(--radius-lg)] space-y-5">
          {step === 0 && (
            <>
              {isSuperAdmin && (
                <FormField label="Organization" required error={fieldErrors.org}>
                  <Select
                    value={orgId}
                    onValueChange={value => {
                      setOrgId(value)
                      setFieldErrors(prev => ({ ...prev, org: undefined }))
                    }}
                    placeholder="Select an organization"
                    options={orgs.map(org => ({ value: org.id!, label: org.name }))}
                  />
                </FormField>
              )}

              <FormField label="Connection Name" required error={fieldErrors.name}>
                <Input
                  value={connectionName}
                  onChange={e => {
                    setConnectionName(e.target.value)
                    setFieldErrors(prev => ({ ...prev, name: undefined }))
                  }}
                  placeholder="Production analytics"
                  leftIcon={<Database className="w-4 h-4" />}
                />
              </FormField>

              <FormField label="Database Type" required>
                <Select
                  value={databaseType}
                  onValueChange={value => setDatabaseType(value as DatabaseConnectionType)}
                  options={DATABASE_TYPE_OPTIONS}
                />
              </FormField>

              {databaseType !== 'firebase' ? (
                <div>
                  <FormField
                    label="Connection String"
                    required
                    error={fieldErrors.connectionString}
                    hint="Stored encrypted - never exposed in API responses"
                  >
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={connectionString}
                      onChange={e => {
                        setConnectionString(e.target.value)
                        setFieldErrors(prev => ({ ...prev, connectionString: undefined }))
                      }}
                      onKeyDown={e => e.key === 'Enter' && !previewing && handlePreview()}
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
                      {getConnectionTypeLabel(databaseType)} format:{' '}
                      <code className="font-mono text-[var(--text-1)]">{CONNECTION_FORMATS[databaseType]}</code>
                    </span>
                  </p>
                </div>
              ) : (
                <>
                  <FormField label="Service Account JSON" required error={fieldErrors.serviceAccount}>
                    <Textarea
                      value={firebaseServiceAccount}
                      onChange={e => {
                        setFirebaseServiceAccount(e.target.value)
                        setFieldErrors(prev => ({ ...prev, serviceAccount: undefined }))
                      }}
                      placeholder='{"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}'
                      className="min-h-[180px] font-mono text-[12px]"
                    />
                  </FormField>
                  <FormField
                    label="Firestore Database ID"
                    hint="Use (default) unless you created a named Firestore database."
                  >
                    <Input
                      value={firebaseDatabaseId}
                      onChange={e => setFirebaseDatabaseId(e.target.value)}
                      leftIcon={<FileJson className="w-4 h-4" />}
                      placeholder={DEFAULT_FIREBASE_DATABASE}
                    />
                  </FormField>
                </>
              )}

              <InfoBox variant="info">
                Clicking &ldquo;Preview&rdquo; connects to your database, fetches the schema, and uses AI to generate descriptions. Nothing is saved yet.
              </InfoBox>

              <div className="flex justify-end gap-2 pt-1">
                <Link href="/client/db-connections">
                  <Button type="button" variant="secondary">Cancel</Button>
                </Link>
                <Button variant="primary" onClick={handlePreview} disabled={previewing}>
                  {previewing ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Connecting &amp; analysing...
                    </>
                  ) : (
                    <>
                      <Database className="w-4 h-4 mr-2" />
                      Preview Connection
                    </>
                  )}
                </Button>
              </div>
            </>
          )}

          {step === 1 && preview && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="neutral">{connectionName.trim()}</Badge>
                <Badge variant="neutral">{getConnectionTypeLabel(connectionType)}</Badge>
                <Badge variant="neutral">
                  {preview.kind.toUpperCase()}{preview.dialect ? ` / ${preview.dialect}` : ''}
                </Badge>
                <Badge variant="info">{preview.table_count} {objectLabel}</Badge>
                <Badge variant="success">{preview.described_count} described</Badge>
              </div>

              {preview.formatted_connection_string && (
                <div className="p-3 rounded-[var(--radius-md)] bg-[var(--surface-2)] border border-[var(--border)] space-y-1">
                  <span className="text-[11px] font-medium text-[var(--text-3)] block uppercase tracking-wider">
                    Formatted Connection String
                  </span>
                  <p className="font-mono text-[12px] text-violet-600 dark:text-violet-400 break-all select-all">
                    {preview.formatted_connection_string}
                  </p>
                </div>
              )}

              <p className="text-[13px] text-[var(--text-2)]">
                Review and edit the AI-generated descriptions below. These help your agents understand each table or collection.
              </p>

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
                      placeholder="Add a description for this table or collection..."
                      className="min-h-[56px] text-[13px]"
                      rows={2}
                    />
                  </div>
                ))}
              </div>

              <div className="flex justify-between gap-2 pt-1">
                <Button variant="secondary" onClick={() => setStep(0)}>
                  Back
                </Button>
                <Button variant="primary" onClick={handleSave} disabled={saving}>
                  {saving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Lock className="w-4 h-4 mr-2" />
                      Save Connection
                    </>
                  )}
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
