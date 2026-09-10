'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  File,
  FileText,
  Image,
  Video,
  Music,
  Archive,
  Code,
  Plus,
  Pencil,
  Trash2,
  Share2,
  X,
  Loader2,
  AlertCircle,
  HardDrive,
  LogOut,
  ExternalLink,
  Copy,
  Check,
  type LucideIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type {
  DriveFile,
  CreateDriveFilePayload,
  RenameDriveFilePayload,
  ShareDriveFilePayload,
} from '@/types'

/* ── Provider config ─────────────────────────────────────────────────────── */

export interface StorageProviderConfig {
  id: 'google-drive' | 'onedrive'
  name: string
  icon: LucideIcon
  description: string
  securityNote: string
  // API methods
  getStatus: () => Promise<{ connected: boolean }>
  getAuthUrl: () => Promise<{ url: string }>
  /** Optional: save OAuth client credentials (Client ID + Secret) */
  configure?: (clientId: string, clientSecret: string) => Promise<{ url?: string }>
  /** Optional: fetch the redirect URI the user must register in their OAuth app */
  getSetupInfo?: () => Promise<{ has_credentials: boolean; redirect_uri: string }>
  disconnect: () => Promise<void>
  listFiles: () => Promise<DriveFile[]>
  createFile: (payload: CreateDriveFilePayload) => Promise<DriveFile>
  renameFile: (id: string, payload: RenameDriveFilePayload) => Promise<DriveFile>
  deleteFile: (id: string) => Promise<void>
  shareFile: (id: string, payload: ShareDriveFilePayload) => Promise<void>
  // Credential panel UI customization
  credentialTitle?: string
  credentialDescription?: string
  credentialHelpUrl?: string
  credentialHelpLabel?: string
  /** Steps 2–N shown after "Go to the {link}" in the credential help box */
  credentialHelpSteps?: string[]
  clientIdPlaceholder?: string
  clientSecretPlaceholder?: string
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function formatFileSize(bytes?: number): string {
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

function fileIcon(mimeType: string, className?: string) {
  const props = { className: cn('w-5 h-5 shrink-0', className) }
  if (!mimeType) return <File {...props} />
  if (mimeType.startsWith('image/')) return <Image {...props} />
  if (mimeType.startsWith('video/')) return <Video {...props} />
  if (mimeType.startsWith('audio/')) return <Music {...props} />
  if (mimeType.includes('zip') || mimeType.includes('tar') || mimeType.includes('rar'))
    return <Archive {...props} />
  if (mimeType.includes('text/') || mimeType.includes('document') || mimeType.includes('sheet'))
    return <FileText {...props} />
  if (mimeType.includes('javascript') || mimeType.includes('json') || mimeType.includes('html'))
    return <Code {...props} />
  return <File {...props} />
}

function mimeTypeLabel(mimeType: string): string {
  if (!mimeType) return 'File'
  if (mimeType === 'application/vnd.google-apps.folder') return 'Folder'
  if (mimeType === 'application/vnd.google-apps.document') return 'Document'
  if (mimeType === 'application/vnd.google-apps.spreadsheet') return 'Spreadsheet'
  if (mimeType === 'application/vnd.google-apps.presentation') return 'Presentation'
  if (mimeType === 'application/vnd.google-apps.drawing') return 'Drawing'
  // OneDrive Graph API types
  if (mimeType === 'folder') return 'Folder'
  if (mimeType === 'file' || mimeType === 'oneNote') return 'File'
  if (mimeType.startsWith('image/')) return 'Image'
  if (mimeType.startsWith('video/')) return 'Video'
  if (mimeType.startsWith('audio/')) return 'Audio'
  if (mimeType.startsWith('text/')) return 'Text'
  if (mimeType.includes('pdf')) return 'PDF'
  return mimeType.split('/').pop()?.replace(/^[a-z]/, c => c.toUpperCase()) ?? 'File'
}

/* ── Connect Screen ──────────────────────────────────────────────────────── */

function ConnectScreen({ config, initialError }: { config: StorageProviderConfig; initialError?: string }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(initialError || '')
  const Icon = config.icon

  // Credentials configuration state
  const [showConfig, setShowConfig] = useState(false)
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [configSaving, setConfigSaving] = useState(false)
  const [configError, setConfigError] = useState('')
  const [redirectUri, setRedirectUri] = useState('')
  const [copied, setCopied] = useState(false)

  const [hasSavedCredentials, setHasSavedCredentials] = useState(true)

  const needsCredentials =
    error.toLowerCase().includes('no credentials') ||
    error.toLowerCase().includes('client id') ||
    error.toLowerCase().includes('client_secret')
  const canShowConfig = (needsCredentials || !hasSavedCredentials) && !!config.configure

  // Check if credentials are already saved; show config panel only if missing
  useEffect(() => {
    if (config.getSetupInfo) {
      config.getSetupInfo().then(info => {
        setHasSavedCredentials(info.has_credentials)
        if (!info.has_credentials || initialError) {
          setShowConfig(true)
        }
        setRedirectUri(info.redirect_uri)
      }).catch(() => {})
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        setLoading(false)
        setConfigSaving(false)
      }
    }
    window.addEventListener('pageshow', handlePageShow)
    return () => window.removeEventListener('pageshow', handlePageShow)
  }, [])

  // Fetch the redirect URI as soon as the config panel is needed
  useEffect(() => {
    if (showConfig && config.getSetupInfo && !redirectUri) {
      config.getSetupInfo().then(info => setRedirectUri(info.redirect_uri)).catch(() => {})
    }
  }, [showConfig, config, redirectUri])

  const handleCopyUri = () => {
    if (!redirectUri) return
    navigator.clipboard.writeText(redirectUri).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleConnect = async () => {
    setLoading(true)
    setError('')
    try {
      const { url } = await config.getAuthUrl()
      window.location.href = url
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to initiate connection'
      setError(msg)
      if (config.configure && (
        msg.toLowerCase().includes('no credentials') ||
        msg.toLowerCase().includes('client id') ||
        msg.toLowerCase().includes('client_secret')
      )) {
        setShowConfig(true)
      }
      setLoading(false)
    }
  }

  const handleSaveCredentials = async () => {
    if (!clientId.trim() || !clientSecret.trim()) {
      setConfigError('Both Client ID and Client Secret are required')
      return
    }
    setConfigSaving(true)
    setConfigError('')
    try {
      if (config.configure) {
        await config.configure(clientId.trim(), clientSecret.trim())
      }
      // Retry connection after saving credentials
      setError('')
      const { url } = await config.getAuthUrl()
      window.location.href = url
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : 'Failed to save credentials')
    } finally {
      setConfigSaving(false)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center p-6">
      <div className="w-full max-w-md animate-slideUpFade">
        <div className="card-1 p-10 text-center">
          {/* Icon */}
          <div className="mx-auto mb-6 flex size-20 items-center justify-center rounded-3xl
            bg-gradient-to-br from-violet-500/15 to-indigo-500/10
            border border-violet-200/50 dark:border-violet-500/20">
            <Icon className="w-10 h-10 text-violet-600 dark:text-violet-400" />
          </div>

          <h1 className="text-2xl font-bold text-[var(--text-1)] tracking-tight">
            {config.name}
          </h1>
          <p className="mt-2 text-[14px] text-[var(--text-2)] leading-relaxed">
            {config.description}
          </p>

          {/* Error banner (hidden when config panel is showing) */}
          {error && !canShowConfig && (
            <div className="mt-4 flex items-center gap-2 rounded-xl bg-red-50 dark:bg-red-900/20
              border border-red-200 dark:border-red-800/50 px-4 py-3 text-[13px] text-red-600 dark:text-red-400 text-left">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* ── Credentials config panel ── */}
          {showConfig && config.configure && (
            <div className="mt-6 text-left rounded-xl border border-amber-200 dark:border-amber-800/50
              bg-amber-50/60 dark:bg-amber-900/10 p-5 space-y-4">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
                <div>
                  <p className="text-[13px] font-semibold text-amber-800 dark:text-amber-300">
                    {config.credentialTitle || `${config.name} credentials required`}
                  </p>
                  <p className="mt-1 text-[12px] text-amber-700/80 dark:text-amber-400/80 leading-relaxed">
                    {config.credentialDescription || `Enter your ${config.name} OAuth Client ID and Secret to enable access.`}
                  </p>
                </div>
              </div>

              {/* Note: where to get credentials */}
              <div className="rounded-lg border border-amber-200/60 dark:border-amber-700/30
                bg-white/60 dark:bg-black/20 p-3 text-[12px] text-[var(--text-2)] leading-relaxed space-y-3">
                <div>
                  <p className="font-medium text-[var(--text-1)] mb-1">How to get your credentials:</p>
                  <ol className="list-decimal list-inside space-y-1 opacity-80">
                    <li>Go to the{' '}
                      <a
                        href={config.credentialHelpUrl || 'https://console.cloud.google.com/apis/credentials'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-violet-600 dark:text-violet-400 hover:underline inline-flex items-center gap-0.5"
                      >
                        {config.credentialHelpLabel || 'provider console'}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </li>
                    {(config.credentialHelpSteps || [
                      'Create an OAuth 2.0 Client ID (Web application type)',
                      'Under Authorized redirect URIs, add the URL below',
                      'Copy the Client ID and Client Secret into the fields below',
                    ]).map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                </div>

                {/* Redirect URI copy box */}
                <div>
                  <p className="font-medium text-[var(--text-1)] mb-1.5">Authorized Redirect URI to register:</p>
                  <div className="flex items-center gap-2 rounded-md border border-amber-300/60 dark:border-amber-600/30
                    bg-amber-50 dark:bg-amber-950/30 px-3 py-2">
                    <code className="flex-1 text-[11px] font-mono text-amber-900 dark:text-amber-200 break-all select-all">
                      {redirectUri || '—'}
                    </code>
                    <button
                      type="button"
                      onClick={handleCopyUri}
                      disabled={!redirectUri}
                      title="Copy redirect URI"
                      className="shrink-0 p-1 rounded text-amber-700 dark:text-amber-400
                        hover:bg-amber-200/60 dark:hover:bg-amber-800/40 transition-colors disabled:opacity-40"
                    >
                      {copied
                        ? <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                        : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Input fields */}
              <div className="space-y-3">
                <div>
                  <label className="block text-[12px] font-semibold text-[var(--text-1)] mb-1">
                    Client ID
                  </label>
                  <Input
                    value={clientId}
                    onChange={e => setClientId(e.target.value)}
                    placeholder={config.clientIdPlaceholder || 'your-client-id'}
                    className="text-[13px]"
                  />
                </div>
                <div>
                  <label className="block text-[12px] font-semibold text-[var(--text-1)] mb-1">
                    Client Secret
                  </label>
                  <Input
                    type="password"
                    value={clientSecret}
                    onChange={e => setClientSecret(e.target.value)}
                    placeholder={config.clientSecretPlaceholder || 'your-client-secret'}
                    className="text-[13px]"
                  />
                </div>
              </div>

              {configError && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-900/20
                  border border-red-200 dark:border-red-800/50 px-3 py-2 text-[12px] text-red-600 dark:text-red-400">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{configError}</span>
                </div>
              )}

              <Button
                variant="primary"
                size="sm"
                className="w-full h-9 text-[13px] font-semibold"
                onClick={handleSaveCredentials}
                disabled={configSaving || !clientId.trim() || !clientSecret.trim()}
              >
                {configSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save & Connect'
                )}
              </Button>
            </div>
          )}

          {/* Connect button (hidden when credential config is showing) */}
          {!showConfig && (
            <div className="mt-8 space-y-3">
              <Button
                variant="primary"
                size="lg"
                className="w-full h-11 text-[15px] font-semibold group relative overflow-hidden"
                onClick={handleConnect}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Redirecting...
                  </>
                ) : (
                  <>
                    <Icon className="w-5 h-5 mr-2 group-hover:scale-110 transition-transform" />
                    Connect {config.name}
                  </>
                )}
              </Button>
              {config.configure && (
                <button
                  type="button"
                  onClick={() => setShowConfig(true)}
                  className="w-full text-center text-[12px] text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors underline underline-offset-2"
                >
                  {error ? 'Fix credentials' : 'Change credentials'}
                </button>
              )}
            </div>
          )}

          <p className="mt-4 text-[12px] text-[var(--text-3)]">
            {config.securityNote}
          </p>
        </div>
      </div>
    </div>
  )
}

/* ── Connected Screen ────────────────────────────────────────────────────── */

type ModalMode = 'create' | 'rename' | 'share' | null

function ConnectedScreen({
  config,
  onDisconnect,
}: {
  config: StorageProviderConfig
  onDisconnect: () => void
}) {
  const [files, setFiles] = useState<DriveFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [disconnecting, setDisconnecting] = useState(false)

  // Modal state
  const [modal, setModal] = useState<ModalMode>(null)
  const [selectedFile, setSelectedFile] = useState<DriveFile | null>(null)
  const [modalValue, setModalValue] = useState('')
  const [modalSubmitting, setModalSubmitting] = useState(false)
  const [modalError, setModalError] = useState('')

  // Deleting state (track per file id)
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())

  const loadFiles = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await config.listFiles()
      setFiles(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load files')
    } finally {
      setLoading(false)
    }
  }, [config])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  /* ── Modal handlers ── */

  const openModal = (mode: ModalMode, file?: DriveFile) => {
    setModal(mode)
    setSelectedFile(file ?? null)
    setModalValue(mode === 'rename' && file ? file.name : '')
    setModalError('')
    setModalSubmitting(false)
  }

  const closeModal = () => {
    setModal(null)
    setSelectedFile(null)
    setModalValue('')
    setModalError('')
  }

  const handleCreate = async () => {
    if (!modalValue.trim()) {
      setModalError('Please enter a file name')
      return
    }
    setModalSubmitting(true)
    setModalError('')
    try {
      await config.createFile({ name: modalValue.trim() })
      closeModal()
      loadFiles()
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to create file')
    } finally {
      setModalSubmitting(false)
    }
  }

  const handleRename = async () => {
    if (!selectedFile || !modalValue.trim()) {
      setModalError('Please enter a file name')
      return
    }
    setModalSubmitting(true)
    setModalError('')
    try {
      await config.renameFile(selectedFile.id, { name: modalValue.trim() })
      closeModal()
      loadFiles()
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to rename file')
    } finally {
      setModalSubmitting(false)
    }
  }

  const handleShare = async () => {
    if (!selectedFile || !modalValue.trim()) {
      setModalError('Please enter an email address')
      return
    }
    setModalSubmitting(true)
    setModalError('')
    try {
      await config.shareFile(selectedFile.id, { email: modalValue.trim() })
      closeModal()
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to share file')
    } finally {
      setModalSubmitting(false)
    }
  }

  const handleDelete = async (file: DriveFile) => {
    setDeletingIds(prev => new Set(prev).add(file.id))
    try {
      await config.deleteFile(file.id)
      setFiles(prev => prev.filter(f => f.id !== file.id))
    } catch (err) {
      loadFiles()
    } finally {
      setDeletingIds(prev => {
        const next = new Set(prev)
        next.delete(file.id)
        return next
      })
    }
  }

  const handleDisconnect = async () => {
    setDisconnecting(true)
    try {
      await config.disconnect()
      onDisconnect()
    } catch {
      onDisconnect()
    }
    window.dispatchEvent(
      new CustomEvent('storage:disconnected', { detail: { providerId: config.id } })
    )
  }

  /* ── Modal dialog ── */

  const modalTitle =
    modal === 'create' ? 'Create file' : modal === 'rename' ? 'Rename file' : modal === 'share' ? 'Share file' : ''
  const modalPlaceholder =
    modal === 'create' ? 'My File' : modal === 'rename' ? 'New name' : 'colleague@example.com'
  const modalAction =
    modal === 'create' ? handleCreate : modal === 'rename' ? handleRename : modal === 'share' ? handleShare : undefined

  return (
    <>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-[22px] font-bold text-[var(--text-1)] tracking-tight">
              {config.name}
            </h1>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 dark:border-emerald-800/50
              bg-emerald-50 dark:bg-emerald-900/20 px-2.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
              <span className="relative flex size-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 dark:bg-emerald-400 opacity-75" />
                <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
              </span>
              Connected
            </span>
          </div>
          <p className="mt-1 text-[13px] text-[var(--text-2)]">
            Manage your {config.name} files
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="primary" size="sm" onClick={() => openModal('create')}>
            <Plus className="w-4 h-4 mr-1.5" />
            New File
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDisconnect}
            disabled={disconnecting}
            className="text-red-600 dark:text-red-400 border-red-200 dark:border-red-800/50
              hover:bg-red-50 dark:hover:bg-red-900/20 hover:border-red-300 dark:hover:border-red-700"
          >
            {disconnecting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogOut className="w-4 h-4" />
            )}
            <span className="hidden sm:inline ml-1.5">Disconnect</span>
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl bg-red-50 dark:bg-red-900/20
          border border-red-200 dark:border-red-800/50 px-4 py-3 text-[13px] text-red-600 dark:text-red-400">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
          <button type="button" onClick={loadFiles} className="ml-auto underline font-medium hover:no-underline">
            Retry
          </button>
        </div>
      )}

      {/* File list */}
      <div className="card-1 overflow-hidden">
        {/* Table header */}
        <div className="hidden sm:grid grid-cols-12 gap-3 px-5 py-3
          border-b border-[var(--border)] bg-[var(--surface-2)]/50">
          <div className="col-span-6 text-[11px] font-bold uppercase tracking-wider text-[var(--text-3)]">Name</div>
          <div className="col-span-3 text-[11px] font-bold uppercase tracking-wider text-[var(--text-3)]">Type</div>
          <div className="col-span-2 text-[11px] font-bold uppercase tracking-wider text-[var(--text-3)]">Size</div>
          <div className="col-span-1" />
        </div>

        {loading ? (
          <div className="p-10 text-center">
            <Loader2 className="w-6 h-6 animate-spin mx-auto text-[var(--text-3)]" />
            <p className="mt-3 text-[13px] text-[var(--text-2)]">Loading files...</p>
          </div>
        ) : files.length === 0 ? (
          <div className="p-12 text-center">
            <HardDrive className="w-10 h-10 mx-auto text-[var(--text-3)] opacity-20" />
            <p className="mt-3 text-[14px] font-medium text-[var(--text-2)]">No files yet</p>
            <p className="mt-1 text-[13px] text-[var(--text-3)]">
              Create a file to get started.
            </p>
            <Button variant="primary" size="sm" className="mt-4" onClick={() => openModal('create')}>
              <Plus className="w-4 h-4 mr-1.5" />
              Create your first file
            </Button>
          </div>
        ) : (
          <div>
            {files.map((file, idx) => (
              <div
                key={file.id}
                className="grid grid-cols-12 gap-3 items-center px-5 py-3.5
                  border-b border-[var(--border)] last:border-b-0
                  hover:bg-black/[0.02] dark:hover:bg-white/[0.03]
                  transition-colors duration-150 group animate-slideUpFade"
                style={{ animationDelay: `${idx * 30}ms` }}
              >
                {/* Name */}
                <div className="col-span-12 sm:col-span-6 flex items-center gap-3 min-w-0">
                  <span className="shrink-0 text-[var(--text-3)]">
                    {fileIcon(file.mime_type)}
                  </span>
                  <span className="text-[14px] font-medium text-[var(--text-1)] truncate">
                    {file.name}
                  </span>
                </div>

                {/* Type */}
                <div className="hidden sm:block col-span-3">
                  <span className="inline-flex items-center rounded-md border border-[var(--border)]
                    bg-[var(--surface-2)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-2)]">
                    {mimeTypeLabel(file.mime_type)}
                  </span>
                </div>

                {/* Size */}
                <div className="hidden sm:block col-span-2 text-[13px] text-[var(--text-3)]">
                  {formatFileSize(file.size)}
                </div>

                {/* Actions */}
                <div className="col-span-12 sm:col-span-1 flex items-center justify-end gap-1">
                  <button
                    type="button"
                    title="Rename"
                    onClick={() => openModal('rename', file)}
                    className="p-1.5 rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)]
                      hover:bg-black/[0.06] dark:hover:bg-white/[0.08]
                      opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    title="Share"
                    onClick={() => openModal('share', file)}
                    className="p-1.5 rounded-lg text-[var(--text-3)] hover:text-blue-600 dark:hover:text-blue-400
                      hover:bg-blue-50 dark:hover:bg-blue-900/20
                      opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                  >
                    <Share2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    title="Delete"
                    onClick={() => handleDelete(file)}
                    disabled={deletingIds.has(file.id)}
                    className="p-1.5 rounded-lg text-[var(--text-3)] hover:text-red-600 dark:hover:text-red-400
                      hover:bg-red-50 dark:hover:bg-red-900/20
                      opacity-0 group-hover:opacity-100 transition-[opacity,background-color,color] duration-150 disabled:opacity-50"
                  >
                    {deletingIds.has(file.id) ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Modal ── */}
      {modal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fadeIn"
          onClick={closeModal}
        >
          <div
            className="w-full max-w-md card-1 p-6 animate-scaleIn"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-[17px] font-bold text-[var(--text-1)]">{modalTitle}</h2>
              <button
                type="button"
                onClick={closeModal}
                className="p-1 rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)]
                  hover:bg-black/[0.06] dark:hover:bg-white/[0.08] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              {modalError && (
                <div className="flex items-center gap-2 rounded-xl bg-red-50 dark:bg-red-900/20
                  border border-red-200 dark:border-red-800/50 px-3.5 py-2.5 text-[13px] text-red-600 dark:text-red-400">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{modalError}</span>
                </div>
              )}

              <Input
                value={modalValue}
                onChange={e => setModalValue(e.target.value)}
                placeholder={modalPlaceholder}
                onKeyDown={e => {
                  if (e.key === 'Enter' && modalAction && !modalSubmitting) modalAction()
                  if (e.key === 'Escape') closeModal()
                }}
                autoFocus
              />

              <div className="flex items-center justify-end gap-2">
                <Button variant="outline" size="sm" onClick={closeModal}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={modalAction}
                  disabled={modalSubmitting || !modalValue.trim()}
                >
                  {modalSubmitting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : modal === 'create' ? (
                    'Create'
                  ) : modal === 'rename' ? (
                    'Rename'
                  ) : (
                    'Share'
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

/* ── Loading / Error wrappers ─────────────────────────────────────────────── */

function LoadingSkeleton() {
  return (
    <div className="min-h-[calc(100vh-200px)] flex items-center justify-center">
      <div className="text-center">
        <Loader2 className="w-8 h-8 animate-spin mx-auto text-violet-500" />
        <p className="mt-4 text-[14px] text-[var(--text-2)]">Checking connection...</p>
      </div>
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="min-h-[calc(100vh-200px)] flex items-center justify-center p-6">
      <div className="w-full max-w-sm text-center card-1 p-8">
        <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl
          bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50">
          <AlertCircle className="w-7 h-7 text-red-500" />
        </div>
        <h2 className="text-[17px] font-bold text-[var(--text-1)]">Connection Error</h2>
        <p className="mt-2 text-[13px] text-[var(--text-2)]">{message}</p>
        <Button variant="primary" size="sm" className="mt-5" onClick={onRetry}>
          Try Again
        </Button>
      </div>
    </div>
  )
}

/* ── Main Manager Component ──────────────────────────────────────────────── */

export default function StorageManager({
  config,
  initialError,
}: {
  config: StorageProviderConfig
  initialError?: string
}) {
  const [status, setStatus] = useState<'loading' | 'error' | 'connect' | 'connected'>(
    initialError ? 'connect' : 'loading'
  )
  const [statusError, setStatusError] = useState(initialError || '')

  const checkStatus = useCallback(async () => {
    setStatus('loading')
    setStatusError('')
    try {
      const { connected } = await config.getStatus()
      setStatus(connected ? 'connected' : 'connect')
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : 'Failed to check connection status')
      setStatus('error')
    }
  }, [config])

  useEffect(() => {
    if (!initialError) {
      checkStatus()
    }
  }, [checkStatus, initialError])

  if (status === 'loading') return <LoadingSkeleton />
  if (status === 'error') return <ErrorState message={statusError} onRetry={checkStatus} />
  if (status === 'connect') return <ConnectScreen config={config} initialError={statusError} />
  if (status === 'connected') return (
    <div className="p-6 max-w-4xl mx-auto">
      <ConnectedScreen config={config} onDisconnect={() => setStatus('connect')} />
    </div>
  )
}
